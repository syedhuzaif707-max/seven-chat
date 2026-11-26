"""Seven Chat - backend (sirf Python standard library, koi install nahi chahiye).

Do AI provider chalte hain:
  1) GEMINI_API_KEY set ho to Google Gemini (free tier) use hota hai.
  2) Nahi to ANTHROPIC_API_KEY set ho to Claude use hota hai (paid).

Chalane ka tareeka:
    export GEMINI_API_KEY="apni-key-yahan"     (Windows: set GEMINI_API_KEY=apni-key-yahan)
    python server.py
Phir browser mein kholo: http://localhost:8000

Optional settings (environment variables):
    AI_PROVIDER        "gemini" ya "anthropic" (agar dono keys hon to yahan se chuno)
    GEMINI_MODEL       Gemini model ka naam (default: gemini-2.5-flash)
    SEVEN_CHAT_MODEL   Claude model ka naam (default: claude-sonnet-5-5)
    RATE_PER_MIN       ek IP se 1 minute mein max messages (default 12)
    RATE_PER_DAY       ek IP se 1 din mein max messages (default 150)
    MAX_BODY_MB        request ka max size MB mein (default 6)
"""
import json
import os
import threading
import time
import urllib.error
import urllib.request
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
PROVIDER = os.environ.get("AI_PROVIDER", "").strip().lower()
if PROVIDER not in ("gemini", "anthropic"):
    PROVIDER = "anthropic" if (ANTHROPIC_KEY and not GEMINI_KEY) else "gemini"

CLAUDE_MODEL = os.environ.get("SEVEN_CHAT_MODEL", "claude-sonnet-5-5")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()
GEMINI_FALLBACKS = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"]
GEMINI_BASE = os.environ.get("GEMINI_BASE", "https://generativelanguage.googleapis.com").rstrip("/")

PORT = int(os.environ.get("PORT", "8000"))
RATE_PER_MIN = int(os.environ.get("RATE_PER_MIN", "12"))
RATE_PER_DAY = int(os.environ.get("RATE_PER_DAY", "150"))
MAX_BODY = int(float(os.environ.get("MAX_BODY_MB", "6")) * 1024 * 1024)

SYSTEM_PROMPT = (
    "Tum Seven Chat ho, ek dostana AI assistant. Seven Chat ke founder Sayyad Huzaif Zafar hain. "
    "User jis bhasha mein likhe (Hindi, Hinglish ya English) usi mein jawab do. "
    "Jawab saaf, chhote aur madadgaar rakho. Agar user photo bheje to use dhyan se dekhkar uske sawal ka jawab do."
)

HERE = os.path.dirname(os.path.abspath(__file__))
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_IMAGE_B64 = 3_000_000
MAX_IMAGES = 3

STATIC = {
    "/": ("index.html", "text/html; charset=utf-8", "no-cache"),
    "/index.html": ("index.html", "text/html; charset=utf-8", "no-cache"),
    "/manifest.json": ("manifest.json", "application/manifest+json", "no-cache"),
    "/sw.js": ("sw.js", "application/javascript; charset=utf-8", "no-cache"),
    "/icon-192.png": ("icon-192.png", "image/png", "public, max-age=86400"),
    "/icon-512.png": ("icon-512.png", "image/png", "public, max-age=86400"),
}

_hits = defaultdict(deque)
_lock = threading.Lock()


class AIError(Exception):
    """User ko dikhane layak message ke saath."""

    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def has_key():
    return bool(GEMINI_KEY if PROVIDER == "gemini" else ANTHROPIC_KEY)


def check_rate(ip):
    now = time.time()
    with _lock:
        q = _hits[ip]
        while q and now - q[0] > 86400:
            q.popleft()
        if len(q) >= RATE_PER_DAY:
            return False, "Aaj ki limit poori ho gayi. Kal dobara try karo."
        if sum(1 for t in q if now - t < 60) >= RATE_PER_MIN:
            return False, "Thoda ruko, bahut jaldi messages ja rahe hain."
        q.append(now)
    return True, ""


def clean_messages(raw):
    if not isinstance(raw, list):
        raise ValueError("Messages ka format galat hai.")
    out = []
    images = 0
    for m in raw[-20:]:
        if not isinstance(m, dict):
            raise ValueError("Messages ka format galat hai.")
        role = m.get("role")
        content = m.get("content")
        if role not in ("user", "assistant"):
            raise ValueError("Messages ka format galat hai.")
        if isinstance(content, str):
            if content.strip():
                out.append({"role": role, "content": content[:8000]})
        elif isinstance(content, list):
            blocks = []
            for b in content:
                if not isinstance(b, dict):
                    raise ValueError("Messages ka format galat hai.")
                kind = b.get("type")
                if kind == "text":
                    text = str(b.get("text", ""))[:8000]
                    if text.strip():
                        blocks.append({"type": "text", "text": text})
                elif kind == "image" and role == "user":
                    src = b.get("source") or {}
                    data = src.get("data", "")
                    if (src.get("type") != "base64" or src.get("media_type") not in ALLOWED_IMAGE_TYPES
                            or not isinstance(data, str)):
                        raise ValueError("Photo ka format sahi nahi hai.")
                    if len(data) > MAX_IMAGE_B64:
                        raise ValueError("Photo bahut badi hai.")
                    images += 1
                    if images > MAX_IMAGES:
                        raise ValueError("Ek saath itni photos nahi bhej sakte.")
                    blocks.append({"type": "image", "source": {
                        "type": "base64", "media_type": src["media_type"], "data": data}})
            if blocks:
                out.append({"role": role, "content": blocks})
    while out and out[0]["role"] != "user":
        out.pop(0)
    if not out:
        raise ValueError("Message khaali hai.")
    return out


def _post_json(url, headers, body, timeout=90):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def ask_claude(messages):
    try:
        data = _post_json(
            "https://api.anthropic.com/v1/messages",
            {"content-type": "application/json", "x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01"},
            {"model": CLAUDE_MODEL, "max_tokens": 1024, "system": SYSTEM_PROMPT, "messages": messages},
        )
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:300]
        print("Claude API error", e.code, detail, flush=True)
        msg = {
            400: "Request mein dikkat hai, ya API credit khatam ho gaya hai.",
            401: "Server ki API key galat hai.",
            403: "API access nahi mila.",
            429: "Abhi bahut load hai, thodi der baad try karo.",
            529: "AI abhi busy hai, thodi der baad try karo.",
        }.get(e.code, f"AI se jawab nahi aaya (error {e.code}).")
        raise AIError(502, msg)
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


def to_gemini_contents(messages):
    contents = []
    for m in messages:
        parts = []
        if isinstance(m["content"], str):
            parts.append({"text": m["content"]})
        else:
            for b in m["content"]:
                if b["type"] == "text":
                    parts.append({"text": b["text"]})
                else:
                    parts.append({"inline_data": {"mime_type": b["source"]["media_type"],
                                                  "data": b["source"]["data"]}})
        contents.append({"role": "user" if m["role"] == "user" else "model", "parts": parts})
    return contents


def ask_gemini(messages):
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": to_gemini_contents(messages),
        "generationConfig": {"maxOutputTokens": 1024},
    }
    headers = {"content-type": "application/json", "x-goog-api-key": GEMINI_KEY}
    models = [GEMINI_MODEL] + [m for m in GEMINI_FALLBACKS if m != GEMINI_MODEL]
    data = None
    for i, model in enumerate(models):
        url = f"{GEMINI_BASE}/v1beta/models/{model}:generateContent"
        try:
            data = _post_json(url, headers, body)
            break
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "ignore")[:400]
            print(f"Gemini API error {e.code} (model {model})", detail, flush=True)
            if e.code == 404 and i < len(models) - 1:
                continue  # ye model nahi mila, agla try karo
            low = detail.lower()
            if e.code in (400, 401, 403) and ("api key" in low or "api_key" in low or e.code in (401, 403)):
                raise AIError(502, "Server ki Gemini API key galat hai.")
            if e.code == 429:
                raise AIError(502, "Free limit poori ho gayi. Thodi der baad try karo.")
            if e.code == 404:
                raise AIError(502, "Gemini model nahi mila. GEMINI_MODEL badalna padega.")
            if e.code >= 500:
                raise AIError(502, "AI abhi busy hai, thodi der baad try karo.")
            raise AIError(502, f"AI se jawab nahi aaya (error {e.code}).")
    if data is None:
        raise AIError(502, "AI se jawab nahi aaya.")
    cands = data.get("candidates") or []
    if not cands:
        if (data.get("promptFeedback") or {}).get("blockReason"):
            return "Maaf karna, main is sawal ka jawab nahi de sakta. Kuch aur poochho."
        return ""
    parts = (cands[0].get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
    if not text and cands[0].get("finishReason") in ("SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT"):
        return "Maaf karna, main is sawal ka jawab nahi de sakta. Kuch aur poochho."
    return text


def ask_ai(messages):
    return ask_gemini(messages) if PROVIDER == "gemini" else ask_claude(messages)


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, content_type, payload, cache=None):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        if cache:
            self.send_header("Cache-Control", cache)
        self.end_headers()
        self.wfile.write(payload)

    def _json(self, code, obj):
        self._send(code, "application/json; charset=utf-8", json.dumps(obj).encode("utf-8"), "no-store")

    def _client_ip(self):
        fwd = self.headers.get("X-Forwarded-For", "")
        return fwd.split(",")[0].strip() or self.client_address[0]

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/health":
            return self._send(200, "text/plain", b"ok")
        item = STATIC.get(path)
        if not item:
            return self._send(404, "text/plain", b"Not found")
        name, ctype, cache = item
        try:
            with open(os.path.join(HERE, name), "rb") as f:
                self._send(200, ctype, f.read(), cache)
        except FileNotFoundError:
            self._send(404, "text/plain", b"Not found")

    def do_POST(self):
        if self.path != "/chat":
            return self._send(404, "text/plain", b"Not found")
        if not has_key():
            name = "GEMINI_API_KEY" if PROVIDER == "gemini" else "ANTHROPIC_API_KEY"
            return self._json(500, {"error": f"Server par {name} set nahi hai."})
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self._json(400, {"error": "Request galat hai."})
        if length <= 0 or length > MAX_BODY:
            return self._json(413, {"error": "Message ya photo bahut badi hai."})
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            messages = clean_messages(payload.get("messages"))
        except (ValueError, json.JSONDecodeError) as e:
            return self._json(400, {"error": str(e) or "Request galat hai."})
        ok, why = check_rate(self._client_ip())
        if not ok:
            return self._json(429, {"error": why})
        try:
            reply = ask_ai(messages)
            self._json(200, {"reply": reply or "(khaali jawab aaya, dobara try karo)"})
        except AIError as e:
            self._json(e.status, {"error": e.message})
        except (urllib.error.URLError, TimeoutError):
            self._json(502, {"error": "AI tak pahunch nahi paaye. Thodi der baad try karo."})
        except Exception as e:
            print("Server error", repr(e), flush=True)
            self._json(500, {"error": "Server mein dikkat aayi."})

    def log_message(self, fmt, *args):
        print("%s - %s" % (self._client_ip(), fmt % args), flush=True)


if __name__ == "__main__":
    print(f"Seven Chat chal raha hai: http://localhost:{PORT} (AI: {PROVIDER})", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
