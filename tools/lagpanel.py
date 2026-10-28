#!/usr/bin/env python3
"""Bygger lag.json: nyckeltal match för match per lag, för lagpanelen (lag.html).

Användning:
    python3 tools/lagpanel.py            # skriver lag.json i repots rot

Läser matcher.json och data/<samma filnamn som matchsidan>.json. Matcher utan
rå-JSON hoppas över. Vårt lag = hemmalaget i JSON om "hemma" är sant, annars bortalaget.
Bara standardbiblioteket.
"""
import json, os, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
from analys import deep_fix, poss, r

ROT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def pct(a, b, n=3):
    return r(a / b, n) if b else None

def nyckeltal(T, us, them):
    s, o = T[us], T[them]
    def g(t, k): return t.get("tot_s" + k, 0) or 0
    fga, fgm = g(s, "FieldGoalsAttempted"), g(s, "FieldGoalsMade")
    tpa, tpm = g(s, "ThreePointersAttempted"), g(s, "ThreePointersMade")
    fta, ftm = g(s, "FreeThrowsAttempted"), g(s, "FreeThrowsMade")
    oreb, dreb, to = g(s, "ReboundsOffensive"), g(s, "ReboundsDefensive"), g(s, "Turnovers")
    o_fga, o_fgm = g(o, "FieldGoalsAttempted"), g(o, "FieldGoalsMade")
    o_tpm, o_fta = g(o, "ThreePointersMade"), g(o, "FreeThrowsAttempted")
    o_oreb, o_dreb, o_to = g(o, "ReboundsOffensive"), g(o, "ReboundsDefensive"), g(o, "Turnovers")
    p_vi, p_de = poss(fga, oreb, to, fta), poss(o_fga, o_oreb, o_to, o_fta)
    return {
        "anfall": r((p_vi + p_de) / 2, 1),
        "ppa": pct(s["score"], p_vi, 2), "ppa_emot": pct(o["score"], p_de, 2),
        "fg": pct(fgm, fga), "p2": pct(fgm - tpm, fga - tpa), "p3": pct(tpm, tpa), "ft": pct(ftm, fta),
        "efg": pct(fgm + 0.5 * tpm, fga), "efg_emot": pct(o_fgm + 0.5 * o_tpm, o_fga),
        "ts": pct(s["score"], 2 * (fga + 0.44 * fta)),
        "tre_andel": pct(tpa, fga), "tre_forsok": tpa, "ft_rate": pct(fta, fga),
        "oreb_andel": pct(oreb, oreb + o_dreb + g(o, "ReboundsTeamDefensive")),
        "dreb_andel": pct(dreb, dreb + o_oreb),
        "oreb": oreb, "oreb_emot": o_oreb,
        "ret": g(s, "ReboundsTotal"), "ret_emot": g(o, "ReboundsTotal"),
        "to_andel": pct(to, p_vi), "to_andel_emot": pct(o_to, p_de), "to": to, "to_emot": o_to,
        "ast": g(s, "Assists"), "ast_andel": pct(g(s, "Assists"), fgm),
        "stl": g(s, "Steals"), "blk": g(s, "Blocks"),
        "p_bollf": g(s, "PointsFromTurnovers"), "p_bollf_emot": g(o, "PointsFromTurnovers"),
        "p_andra": g(s, "PointsSecondChance"), "p_andra_emot": g(o, "PointsSecondChance"),
        "p_snabb": g(s, "PointsFastBreak"), "p_snabb_emot": g(o, "PointsFastBreak"),
        "p_mal": g(s, "PointsInThePaint"), "p_mal_emot": g(o, "PointsInThePaint"),
        "p_bank": g(s, "BenchPoints"),
        "storsta_ledning": g(s, "BiggestLead"), "storsta_ledning_emot": g(o, "BiggestLead"),
    }

def main():
    idx = json.load(open(os.path.join(ROT, "matcher.json"), encoding="utf-8"))["matcher"]
    lag = defaultdict(list)
    for m in sorted(idx, key=lambda m: m["datum"]):
        stem = os.path.splitext(os.path.basename(m["url"]))[0]
        fil = os.path.join(ROT, "data", stem + ".json")
        if not os.path.exists(fil):
            print(f"hoppar över {stem}: ingen data", file=sys.stderr)
            continue
        d = deep_fix(json.load(open(fil, encoding="utf-8")))
        us, them = ("1", "2") if m["hemma"] else ("2", "1")
        T = d["tm"]
        if [T[us]["score"], T[them]["score"]] != [m["for"], m["emot"]]:
            print(f"varning {stem}: resultatet i data stämmer inte med matcher.json", file=sys.stderr)
        rad = {"datum": m["datum"], "motstandare": m["motstandare"], "hemma": m["hemma"],
               "for": m["for"], "emot": m["emot"], "url": m["url"],
               "fl": len([k for k in T[us] if k.startswith("p") and k.endswith("_score") and int(k[1:-6]) > d.get("periodsMax", 4) and T[us][k] is not None]) > 0}
        rad.update(nyckeltal(T, us, them))
        lag[m["lag"]].append(rad)
    ut = {"lag": [{"namn": k, "matcher": v} for k, v in sorted(lag.items(), key=lambda kv: (-len(kv[1]), kv[0]))]}
    with open(os.path.join(ROT, "lag.json"), "w", encoding="utf-8") as f:
        json.dump(ut, f, ensure_ascii=False, indent=1)
    for l in ut["lag"]:
        print(f'{l["namn"]}: {len(l["matcher"])} matcher', file=sys.stderr)

if __name__ == "__main__":
    main()
