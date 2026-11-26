# Seven Chat

AI chat app (web + phone par install hone wali app). Founder: Sayyad Huzaif Zafar.

## Files (sab ek hi folder mein, repo ke root par)
- `server.py` : backend (Python, koi package install nahi)
- `index.html` : chat screen
- `manifest.json`, `sw.js`, `icon-192.png`, `icon-512.png` : app install ke liye

## Computer par chalana
1. `export ANTHROPIC_API_KEY="tumhari-key"` (Windows: `set ANTHROPIC_API_KEY=tumhari-key`)
2. `python server.py`
3. Browser mein `http://localhost:8000` kholo

## Render par daalna (free)
1. Sab files GitHub repo mein upload karo.
2. Render.com par New, phir Web Service, aur apna repo chuno.
3. Runtime: Python, Build Command: `echo ok`, Start Command: `python server.py`
4. Environment Variables mein `ANTHROPIC_API_KEY` daalo.
5. Deploy dabao. Link milne ke baad Chrome mein kholo aur menu mein "App install karo" ya "Add to Home screen" dabao.

## Settings (optional, Environment Variables)
- `RATE_PER_MIN` (default 12) : ek IP se 1 minute mein max messages
- `RATE_PER_DAY` (default 150) : ek IP se 1 din mein max messages
- `SEVEN_CHAT_MODEL` : model badalna ho to

## Dhyan rakho
- API key kabhi `index.html` ya GitHub repo mein mat likhna, sirf Render ke Environment Variables mein.
- Chat history aur photos sirf us phone ke browser mein save hoti hain (server par nahi).
- Voice ke liye Chrome (Android) sahi chalta hai, aur site HTTPS par honi chahiye.
