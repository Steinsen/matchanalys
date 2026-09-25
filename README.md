# Matchanalyser

Statisk sajt med matchanalyser, publicerad via Cloudflare Workers (static assets, kopplad till detta repo).

## Struktur
- `index.html` – startsida med sök (läser `matcher.json`)
- `matcher.json` – en post per analyserad match
- `matcher/ÅÅÅÅ-MM-DD-lag-motstandare.html` – en fristående analyssida per match
- `assets/matchanalys.css` – gemensam stil (kopieras inline i varje matchsida så att sidan även fungerar som lös fil)
- `tools/analys.py` – räknar fram statistik, femmor, on/off, poäng per anfall och ledningsdiagram ur Genius-JSON
- `mallar/match-mall.html` – sektionsordning för en matchsida
- `data/` – rå Genius-JSON per match (för att kunna räkna om)

## Ny match
1. Spara Genius-JSON som `data/ÅÅÅÅ-MM-DD-lag-motstandare.json`.
2. Be Claude göra en matchanalys (skillen "matchanalys").
3. Commit + push → Cloudflare publicerar automatiskt.

## Cloudflare
`wrangler.jsonc` publicerar repots filer som statiska assets (Worker `matcher`, `workers.dev`-URL påslagen).
`.assetsignore` håller `tools/`, `mallar/`, `data/` m.m. utanför sajten.
Build command: *(tomt)* · Deploy command: `npx wrangler deploy`
