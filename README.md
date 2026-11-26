# Seven Chat

AI chat app (web + phone par install hone wali app). Founder: Sayyad Huzaif Zafar.

## Files (sab ek hi folder mein, repo ke root par)
- `server.py` : backend (Python, koi package install nahi)
- `index.html` : chat screen
- `manifest.json`, `sw.js`, `icon-192.png`, `icon-512.png` : app install ke liye

## AI key (do raaste)
- **Free:** Google Gemini. aistudio.google.com/apikey se key lo, Render mein `GEMINI_API_KEY` naam se daalo.
- **Paid:** Claude. console.anthropic.com se key lo, Render mein `ANTHROPIC_API_KEY` naam se daalo.
Dono hon to Gemini chalta hai. (`AI_PROVIDER=anthropic` se Claude chuna ja sakta hai.)

## Computer par chalana
1. `export GEMINI_API_KEY="tumhari-key"` (Windows: `set GEMINI_API_KEY=tumhari-key`)
2. `python server.py`
3. Browser mein `http://localhost:8000` kholo

## Render par daalna (free)
1. Sab files GitHub repo mein upload karo.
2. Render.com par New, phir Web Service, aur apna repo chuno.
3. Runtime: Python, Build Command: `echo ok`, Start Command: `python server.py`
4. Environment Variables mein `GEMINI_API_KEY` daalo.
5. Deploy dabao. Link milne ke baad Chrome mein kholo aur menu mein "App install karo" ya "Add to Home screen" dabao.

## Settings (optional, Environment Variables)
- `GEMINI_MODEL` (default gemini-2.5-flash) : model nahi mile to server khud doosra free model try karta hai
- `RATE_PER_MIN` (default 12) : ek IP se 1 minute mein max messages
- `RATE_PER_DAY` (default 150) : ek IP se 1 din mein max messages

## Dhyan rakho
- API key kabhi `index.html` ya GitHub repo mein mat likhna, sirf Render ke Environment Variables mein.
- Chat history aur photos sirf us phone ke browser mein save hoti hain (server par nahi).
- Voice ke liye Chrome (Android) sahi chalta hai, aur site HTTPS par honi chahiye.
- Free Gemini ki limits hoti hain (kuch messages per minute/din). Zyada users ho to limit poori ho sakti hai.
