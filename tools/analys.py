#!/usr/bin/env python3
"""Matchanalys från Genius Sports live-JSON (FIBA LiveStats-format).

Användning:
    python3 tools/analys.py match.json --lag 1 > analys.json
    python3 tools/analys.py match.json --lag 1 --svg lead.svg

--lag  = vilket lag analysen utgår från ("1" = hemmalag i JSON, "2" = bortalag).
Skriver JSON med lagstatistik, fyra faktorer, anfall, periodresultat, ledningskurva,
poängtorka, ryck, spelarstatistik, on/off, femmor och par. Bara standardbiblioteket.
"""
import argparse, json, sys, itertools
from collections import defaultdict

# ---------- hjälpfunktioner ----------
def fix(s):
    """Rättar dubbelkodad UTF-8 (t.ex. 'LuleÃ¥' -> 'Luleå')."""
    if isinstance(s, str):
        try:
            return s.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return s
    return s

def deep_fix(o):
    if isinstance(o, dict):
        return {fix(k): deep_fix(v) for k, v in o.items()}
    if isinstance(o, list):
        return [deep_fix(v) for v in o]
    return fix(o)

def plen(d, per):
    reg = d.get("periodsMax", 4)
    mins = d.get("periodLengthREGULAR", 10) if per <= reg else d.get("periodLengthOVERTIME", 5)
    return mins * 60

def elapsed(d, a):
    """Sekunder sedan matchstart för en händelse."""
    per = a["period"]
    base = sum(plen(d, p) for p in range(1, per))
    parts = a.get("clock", a.get("gt", "0:0")).split(":")
    rem = int(parts[0]) * 60 + int(parts[1]) + (int(parts[2]) / 100 if len(parts) > 2 else 0)
    return base + plen(d, per) - rem

def mmss(sec):
    sec = round(sec)
    return f"{sec // 60}:{sec % 60:02d}"

def poss(fga, oreb, to, fta):
    return fga - oreb + to + 0.44 * fta

def r(x, n=3):
    return None if x is None else round(x, n)

# ---------- analys ----------
def analyse(d, us):
    them = "2" if us == "1" else "1"
    T = d["tm"]
    out = {"lag": T[us]["name"], "motstandare": T[them]["name"],
           "resultat": [T[us]["score"], T[them]["score"]], "publik": d.get("attendance")}

    # periodresultat
    pers = sorted({int(k[1:-6]) for k in T[us] if k.startswith("p") and k.endswith("_score")})
    out["perioder"] = [{"period": p, "for": T[us].get(f"p{p}_score"), "emot": T[them].get(f"p{p}_score")}
                       for p in pers if T[us].get(f"p{p}_score") is not None]

    # lagstatistik + fyra faktorer
    def team(t, o):
        s = T[t]; os_ = T[o]
        fga, fta, oreb, to = s["tot_sFieldGoalsAttempted"], s["tot_sFreeThrowsAttempted"], s["tot_sReboundsOffensive"], s["tot_sTurnovers"]
        p = poss(fga, oreb, to, fta)
        opp_dreb = os_["tot_sReboundsDefensive"] + os_.get("tot_sReboundsTeamDefensive", 0)
        keys = ["FieldGoalsMade", "FieldGoalsAttempted", "ThreePointersMade", "ThreePointersAttempted",
                "FreeThrowsMade", "FreeThrowsAttempted", "ReboundsOffensive", "ReboundsDefensive", "ReboundsTotal",
                "Assists", "Turnovers", "Steals", "Blocks", "FoulsPersonal", "PointsFromTurnovers",
                "PointsSecondChance", "PointsFastBreak", "BenchPoints", "PointsInThePaint", "BiggestLead",
                "BiggestScoringRun", "TimeLeading", "LeadChanges", "TimesScoresLevel"]
        st = {k: s.get("tot_s" + k) for k in keys}
        st.update({
            "poang": s["score"],
            "anfall": r(p, 1),
            "poang_per_anfall": r(s["score"] / p),
            "efg": r((s["tot_sFieldGoalsMade"] + 0.5 * s["tot_sThreePointersMade"]) / fga),
            "ts": r(s["score"] / (2 * (fga + 0.44 * fta))),
            "to_andel": r(to / p),
            "oreb_andel": r(oreb / (oreb + opp_dreb)),
            "ftm_per_fga": r(s["tot_sFreeThrowsMade"] / fga),
            "assist_andel": r(s["tot_sAssists"] / s["tot_sFieldGoalsMade"]),
        })
        return st
    out["lagstat"] = {"vi": team(us, them), "de": team(them, us)}

    # spelare
    def players(t):
        res = {}
        for pno, p in T[t]["pl"].items():
            fga, fta = p["sFieldGoalsAttempted"], p["sFreeThrowsAttempted"]
            res[pno] = {
                "namn": f'{p["firstName"]} {p["familyName"]}', "kort": p.get("scoreboardName"),
                "nr": p["shirtNumber"], "pos": p.get("playingPosition"), "start": p.get("starter", 0) == 1,
                "kapten": p.get("captain", 0) == 1, "min": p["sMinutes"], "p": p["sPoints"],
                "fg": f'{p["sFieldGoalsMade"]}/{fga}', "3p": f'{p["sThreePointersMade"]}/{p["sThreePointersAttempted"]}',
                "ft": f'{p["sFreeThrowsMade"]}/{fta}', "ret": p["sReboundsTotal"], "oret": p["sReboundsOffensive"],
                "ast": p["sAssists"], "to": p["sTurnovers"], "stl": p["sSteals"], "blk": p["sBlocks"],
                "fouls": p["sFoulsPersonal"], "fouls_on": p["sFoulsOn"], "pm_officiell": p["sPlusMinusPoints"],
                "ts": r(p["sPoints"] / (2 * (fga + 0.44 * fta))) if fga + fta else None,
                "eff": p.get("eff_1"),
            }
        return res
    PL = {us: players(us), them: players(them)}

    # ---------- play-by-play: stints ----------
    pbp = sorted(d["pbp"], key=lambda a: a["actionNumber"])
    on = {t: {pno for pno, p in T[t]["pl"].items() if p.get("starter", 0) == 1} for t in ("1", "2")}
    warn = []
    stints = defaultdict(lambda: defaultdict(float))  # (t, frozenset) -> counters
    last_t, s1, s2 = 0.0, 0, 0
    lead_pts = [(0.0, 0)]
    scoring = []  # (t_sec, tno, pts, s1, s2, period, gt)
    sign = 1 if us == "1" else -1

    def add(t, k, v):
        stints[(t, frozenset(on[t]))][k] += v

    for a in pbp:
        if a.get("actionType") == "game":
            continue
        t = elapsed(d, a)
        dt = t - last_t
        if dt > 0:
            for tm_ in ("1", "2"):
                add(tm_, "sek", dt)
            last_t = t
        at, tno, pno = a.get("actionType"), str(a.get("tno")), str(a.get("pno"))
        if at == "substitution" and tno in ("1", "2"):
            (on[tno].add if a.get("subType") == "in" else on[tno].discard)(pno)
            continue
        # poäng
        n1, n2 = int(a.get("s1") or s1), int(a.get("s2") or s2)
        if (n1, n2) != (s1, s2):
            d1, d2 = n1 - s1, n2 - s2
            for tm_, pf, pa in (("1", d1, d2), ("2", d2, d1)):
                if len(on[tm_]) != 5:
                    warn.append(f"Lag {tm_} har {len(on[tm_])} spelare på plan vid händelse {a['actionNumber']}")
                add(tm_, "pf", pf); add(tm_, "pa", pa)
            scorer = "1" if d1 > 0 else "2"
            scoring.append((t, scorer, d1 + d2, n1, n2, a["period"], a.get("gt")))
            s1, s2 = n1, n2
            lead_pts.append((t / 60, sign * (s1 - s2)))
        # anfallskomponenter
        if tno in ("1", "2"):
            opp = "2" if tno == "1" else "1"
            comp = None
            if at in ("2pt", "3pt"): comp = "fga"
            elif at == "freethrow": comp = "fta"
            elif at == "rebound" and a.get("subType") == "offensive": comp = "oreb"
            elif at == "turnover": comp = "to"
            if comp:
                add(tno, "o_" + comp, 1); add(opp, "d_" + comp, 1)

    total_sec = last_t
    if lead_pts[-1][0] < total_sec / 60:
        lead_pts.append((total_sec / 60, lead_pts[-1][1]))
    out["ledning"] = [[r(x, 2), y] for x, y in lead_pts]
    out["warnings"] = sorted(set(warn))[:20]

    # femmor för vårt lag
    def name(pno): return PL[us][pno]["kort"] or PL[us][pno]["namn"]
    fives = []
    for (t, lu), c in stints.items():
        if t != us or c["sek"] <= 0 and c["pf"] == 0 and c["pa"] == 0:
            continue
        po = poss(c["o_fga"], c["o_oreb"], c["o_to"], c["o_fta"])
        pd = poss(c["d_fga"], c["d_oreb"], c["d_to"], c["d_fta"])
        fives.append({"spelare": sorted(name(p) for p in lu), "pno": sorted(lu), "tid": mmss(c["sek"]), "sek": round(c["sek"]),
                      "for": int(c["pf"]), "emot": int(c["pa"]), "pm": int(c["pf"] - c["pa"]),
                      "anfall_for": r(po, 1), "anfall_emot": r(pd, 1),
                      "ppa_for": r(c["pf"] / po, 2) if po > 0 else None,
                      "ppa_emot": r(c["pa"] / pd, 2) if pd > 0 else None})
    fives.sort(key=lambda f: -f["sek"])
    out["femmor"] = fives
    out["femmor_summa_pm"] = sum(f["pm"] for f in fives)

    # on/off per spelare (vårt lag) + kontroll mot officiell +/-
    tot = {"sek": 0, "pf": 0, "pa": 0, "po": 0.0, "pd": 0.0}
    for (t, lu), c in stints.items():
        if t == us:
            tot["sek"] += c["sek"]; tot["pf"] += c["pf"]; tot["pa"] += c["pa"]
            tot["po"] += poss(c["o_fga"], c["o_oreb"], c["o_to"], c["o_fta"])
            tot["pd"] += poss(c["d_fga"], c["d_oreb"], c["d_to"], c["d_fta"])
    for pno, p in PL[us].items():
        o = {"sek": 0, "pf": 0, "pa": 0, "po": 0.0, "pd": 0.0}
        for (t, lu), c in stints.items():
            if t == us and pno in lu:
                o["sek"] += c["sek"]; o["pf"] += c["pf"]; o["pa"] += c["pa"]
                o["po"] += poss(c["o_fga"], c["o_oreb"], c["o_to"], c["o_fta"])
                o["pd"] += poss(c["d_fga"], c["d_oreb"], c["d_to"], c["d_fta"])
        off = {k: tot[k] - o[k] for k in o}
        def blk(x):
            return {"tid": mmss(x["sek"]), "for": int(x["pf"]), "emot": int(x["pa"]), "pm": int(x["pf"] - x["pa"]),
                    "ppa_for": r(x["pf"] / x["po"], 2) if x["po"] > 0 else None,
                    "ppa_emot": r(x["pa"] / x["pd"], 2) if x["pd"] > 0 else None}
        p["pa_plan"] = blk(o); p["pa_bank"] = blk(off)
        p["pm_diff_mot_officiell"] = p["pa_plan"]["pm"] - p["pm_officiell"]
    out["spelare"] = sorted(PL[us].values(), key=lambda p: -p["sek"] if "sek" in p else -int(p["min"].split(":")[0]) * 60 - int(p["min"].split(":")[1]))
    out["motstandare_spelare"] = sorted(PL[them].values(), key=lambda p: -p["p"])

    # par (minst 5 min ihop)
    pairs = []
    for a_, b_ in itertools.combinations(PL[us].keys(), 2):
        x = {"sek": 0, "pf": 0, "pa": 0}
        for (t, lu), c in stints.items():
            if t == us and a_ in lu and b_ in lu:
                x["sek"] += c["sek"]; x["pf"] += c["pf"]; x["pa"] += c["pa"]
        if x["sek"] >= 300:
            pairs.append({"spelare": [name(a_), name(b_)], "tid": mmss(x["sek"]), "pm": int(x["pf"] - x["pa"]),
                          "for": int(x["pf"]), "emot": int(x["pa"])})
    pairs.sort(key=lambda p: -p["pm"])
    out["par_basta"] = pairs[:5]; out["par_samsta"] = pairs[-5:][::-1]

    # poängtorka och ryck
    def droughts(t):
        own = [s for s in scoring if s[1] == t]
        res, prev = [], (0.0, None, 0, 0, 0, 1, "10:00")
        for s in own + [(total_sec, t, 0, s1, s2, None, "slut")]:
            gap = s[0] - prev[0]
            res.append({"langd": mmss(gap), "sek": round(gap), "fran_min": r(prev[0] / 60, 2), "till_min": r(s[0] / 60, 2),
                        "fran_stallning": [prev[3 if us == "1" else 4], prev[4 if us == "1" else 3]],
                        "till_stallning": [s[3 if us == "1" else 4], s[4 if us == "1" else 3]]})
            prev = s
        return sorted(res, key=lambda x: -x["sek"])[:3]
    out["torka_vi"] = droughts(us); out["torka_de"] = droughts(them)
    runs, cur_t, cur_p, start = [], None, 0, None
    for s in scoring:
        if s[1] == cur_t:
            cur_p += s[2]
        else:
            if cur_t: runs.append((cur_p, cur_t, start, prev_s))
            cur_t, cur_p, start = s[1], s[2], s
        prev_s = s
    if cur_t: runs.append((cur_p, cur_t, start, prev_s))
    runs.sort(key=lambda x: -x[0])
    out["ryck"] = [{"lag": "vi" if t == us else "de", "poang": p, "fran_min": r(a[0] / 60, 2), "till_min": r(b[0] / 60, 2),
                    "stallning_efter": [b[3], b[4]] if us == "1" else [b[4], b[3]]} for p, t, a, b in runs[:6]]
    return out

# ---------- ledningsdiagram (SVG, temafärger via CSS-variabler) ----------
def lead_svg(pts, periods=4, plen_min=10, events=()):
    total = max(x for x, _ in pts)
    lo = min(-5, min(y for _, y in pts) - 1); hi = max(12, max(y for _, y in pts) + 1)
    W, H, L, R, T, B = 340, 190, 26, 8, 14, 26
    X = lambda t: L + t / total * (W - L - R)
    Y = lambda v: T + (hi - v) / (hi - lo) * (H - T - B)
    step = []
    for i, (t, v) in enumerate(pts):
        if i: step.append((t, pts[i - 1][1]))
        step.append((t, v))
    poly = " ".join(f"{X(t):.1f},{Y(v):.1f}" for t, v in step)
    area = f"{X(0):.1f},{Y(0):.1f} {poly} {X(total):.1f},{Y(0):.1f}"
    o = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Ledningen under matchen" xmlns="http://www.w3.org/2000/svg" font-size="11.5">',
         f'<defs><clipPath id="up"><rect x="0" y="0" width="{W}" height="{Y(0):.1f}"/></clipPath><clipPath id="dn"><rect x="0" y="{Y(0):.1f}" width="{W}" height="{H}"/></clipPath></defs>']
    for (a, b, label) in events:  # gråmarkerade intervall, t.ex. poängtorka
        o.append(f'<rect x="{X(a):.1f}" y="{T}" width="{X(b) - X(a):.1f}" height="{H - T - B}" fill="var(--warnbg)"/>'
                 f'<text x="{(X(a) + X(b)) / 2:.1f}" y="{T + 11}" text-anchor="middle" fill="var(--warn)" font-size="10">{label}</text>')
    stepv = 4 if hi - lo <= 24 else 8
    v = (lo // stepv) * stepv
    while v <= hi:
        if v >= lo:
            o.append(f'<line x1="{L}" x2="{W - R}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="{"var(--axis)" if v == 0 else "var(--grid)"}" stroke-width="{0.8 if v == 0 else 0.5}"/>'
                     f'<text x="{L - 4}" y="{Y(v) + 3:.1f}" text-anchor="end" fill="var(--muted)">{"+" if v > 0 else ""}{v}</text>')
        v += stepv
    nper = round(total / plen_min) if total > periods * plen_min else periods
    for i in range(1, periods):
        o.append(f'<line x1="{X(i * plen_min):.1f}" x2="{X(i * plen_min):.1f}" y1="{T}" y2="{H - B}" stroke="var(--axis)" stroke-dasharray="2 2" stroke-width="0.6"/>')
    for i in range(periods):
        o.append(f'<text x="{X(i * plen_min + plen_min / 2):.1f}" y="{H - B + 13}" text-anchor="middle" fill="var(--muted)">P{i + 1}</text>')
    if total > periods * plen_min:
        o.append(f'<text x="{X((periods * plen_min + total) / 2):.1f}" y="{H - B + 13}" text-anchor="middle" fill="var(--muted)">FL</text>')
    o.append(f'<polygon points="{area}" fill="var(--accent)" opacity="0.18" clip-path="url(#up)"/><polygon points="{area}" fill="var(--neg)" opacity="0.22" clip-path="url(#dn)"/>')
    o.append(f'<polyline points="{poly}" fill="none" stroke="var(--accent)" stroke-width="1.4" stroke-linejoin="round"/>')
    mx = max(pts, key=lambda p: p[1]); mn = min(pts, key=lambda p: p[1])
    if mx[1] > 0:
        o.append(f'<circle cx="{X(mx[0]):.1f}" cy="{Y(mx[1]):.1f}" r="2.3" fill="var(--accent)"/><text x="{X(mx[0]) - 4:.1f}" y="{Y(mx[1]) - 5:.1f}" text-anchor="end" fill="var(--accent)" font-weight="600" font-size="10.5">+{mx[1]}</text>')
    if mn[1] < 0:
        o.append(f'<circle cx="{X(mn[0]):.1f}" cy="{Y(mn[1]):.1f}" r="2.3" fill="var(--neg)"/><text x="{X(mn[0]) + 5:.1f}" y="{Y(mn[1]) + 4:.1f}" fill="var(--neg)" font-weight="600" font-size="10.5">{mn[1]}</text>')
    o.append(f'<text x="{(L + W - R) / 2}" y="{H - 2}" text-anchor="middle" fill="var(--muted)" font-size="10.5">Ledning i poäng under matchen (över noll = vi leder)</text></svg>')
    return "".join(o)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("fil"); ap.add_argument("--lag", default="1", choices=["1", "2"])
    ap.add_argument("--svg", help="skriv ledningsdiagram till denna fil")
    ap.add_argument("--torka", action="store_true", help="markera vårt lags längsta poängtorka i diagrammet")
    a = ap.parse_args()
    raw = open(a.fil, encoding="utf-8").read()
    data = deep_fix(json.loads(raw))
    res = analyse(data, a.lag)
    if a.svg:
        ev = []
        if a.torka and res["torka_vi"]:
            t0 = res["torka_vi"][0]; ev.append((t0["fran_min"], t0["till_min"], "Torka"))
        open(a.svg, "w", encoding="utf-8").write(lead_svg([tuple(p) for p in res["ledning"]],
            data.get("periodsMax", 4), data.get("periodLengthREGULAR", 10), ev))
    json.dump(res, sys.stdout, ensure_ascii=False, indent=1)
