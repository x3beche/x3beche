#!/usr/bin/env python3
"""Profile stats cards: assets/card-*-{dark,light}.svg from GitHub GraphQL + x3beche.github.io.

Needs GH_TOKEN (a token that can read the user's contribution data; private
contributions only appear as counts). Usage: gen_stats.py [outdir]
"""
import collections, datetime as dt, json, os, re, sys, urllib.request
from html import escape

USER = "x3beche"
SITE = "https://x3beche.github.io/"
OUT = sys.argv[1] if len(sys.argv) > 1 else "."


def gql(query):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": "bearer " + os.environ["GH_TOKEN"], "User-Agent": USER},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        body = json.load(r)
    if "errors" in body:
        raise SystemExit(body["errors"])
    return body["data"]


years = gql('{user(login:"%s"){contributionsCollection{contributionYears}}}' % USER)[
    "user"]["contributionsCollection"]["contributionYears"]

days, per_year, repos = {}, {}, collections.Counter()
for y in sorted(years):
    c = gql(
        '{user(login:"%s"){contributionsCollection(from:"%d-01-01T00:00:00Z",to:"%d-12-31T23:59:59Z"){'
        "restrictedContributionsCount contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}"
        " commitContributionsByRepository(maxRepositories:25){repository{name isPrivate} contributions{totalCount}}}}}" % (USER, y, y)
    )["user"]["contributionsCollection"]
    cal = c["contributionCalendar"]
    for w in cal["weeks"]:
        for d in w["contributionDays"]:
            days[d["date"]] = d["contributionCount"]
    private = c["restrictedContributionsCount"]
    per_year[y] = (cal["totalContributions"] - private, private)
    for r in c["commitContributionsByRepository"]:
        if not r["repository"]["isPrivate"] and r["repository"]["name"] != USER:
            repos[r["repository"]["name"]] += r["contributions"]["totalCount"]

today = dt.date.today()
days = {d: v for d, v in days.items() if dt.date.fromisoformat(d) <= today}
dates = sorted(days)
total = sum(days.values())
active = sum(1 for v in days.values() if v)
first = next(d for d in dates if days[d])
longest = run = 0
for d in dates:
    run = run + 1 if days[d] else 0
    longest = max(longest, run)
current, d = 0, today if days.get(today.isoformat()) else today - dt.timedelta(days=1)
while days.get(d.isoformat()):
    current += 1
    d -= dt.timedelta(days=1)
active_year = sum(1 for d, v in days.items() if v and d.startswith(str(today.year)))
busy_day, busy_n = max(days.items(), key=lambda x: (x[1], x[0]))
this_year = sum(per_year.get(today.year, (0, 0)))

months = []
m = dt.date(today.year, today.month, 1)
for _ in range(12):
    months.append(m)
    m = (m - dt.timedelta(days=1)).replace(day=1)
months.reverse()
month_tot = collections.Counter(d[:7] for d in [])
for d, v in days.items():
    month_tot[d[:7]] += v

wd_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
wd = [0] * 7
for d, v in days.items():
    wd[dt.date.fromisoformat(d).weekday()] += v

site = {}
try:
    html = urllib.request.urlopen(urllib.request.Request(SITE, headers={"User-Agent": USER}), timeout=30).read().decode()
    for n, l in re.findall(r'deck-stat-n[^>]*>([^<]+)</span>\s*<span class="deck-stat-l">([^<]+)<', html):
        site[l.strip()] = n.strip()
    site["Deck"] = str(len(re.findall(r'class="archive-card"', html)))
except Exception as e:  # site down: card renders without the site row
    print("site stats skipped:", e, file=sys.stderr)

TR_MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def fmt(n):
    return f"{n:,}"




# ---------------------------------------------------------------------------
# Rendering: four cards, each in a dark and a light version
#   card-numbers  headline numbers
#   card-clock    every month since the first contribution, one ring per year
#   card-split    where / when / what (three donuts)
#   card-decks    the decks on x3beche.github.io, sized by guide count
# ---------------------------------------------------------------------------
import math

MONO = "'IBM Plex Mono',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
THEMES = {
    "dark": dict(bg="#0b0d10", rule="#2a2f37", text="#e6e8eb", faint="#8b9098", faint2="#5a6068",
                 link="#9ab6ff", cell="#15191e", ramp=["#9ab6ff", "#6f86c4", "#4a5a85", "#34405e", "#262e42", "#1b2130"]),
    "light": dict(bg="#ffffff", rule="#d8dce1", text="#1d2127", faint="#6b717a", faint2="#9aa0a8",
                  link="#3d63d6", cell="#eef0f3", ramp=["#3d63d6", "#6f8ce0", "#9db0ea", "#c3d0f2", "#dde5f8", "#eef2fb"]),
}

since = f"{TR_MON[int(first[5:7])-1]} {first[:4]}"
decks = []
try:
    decks = [(n, int(c)) for n, c in re.findall(
        r'class="archive-name">([^<]+)</span>.*?class="archive-count">(\d+)', html, re.S)]
except NameError:  # site fetch failed
    pass


class Svg:
    def __init__(s, w, h, t):
        s.w, s.h, s.t = w, h, t
        s.o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
               f'font-family="{MONO}"><rect width="{w}" height="{h}" fill="{t["bg"]}"/>']

    def tx(s, x, y, txt, col, size=10, anchor="start", ls=0, weight=400):
        s.o.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" letter-spacing="{ls}" text-anchor="{anchor}" '
                   f'font-weight="{weight}" fill="{col}">{escape(str(txt))}</text>')

    def r(s, x, y, w, h, col, extra=""):
        s.o.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(w,0):.1f}" height="{max(h,0):.1f}" fill="{col}" {extra}/>')

    def ln(s, x1, y1, x2, y2, col):
        s.o.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{col}"/>')

    def label(s, x, y, txt, anchor="start"):
        s.tx(x, y, txt.upper(), s.t["faint"], 9, anchor=anchor, ls=1.6)

    def save(s, path):
        s.o.append("</svg>")
        with open(path, "w") as f:
            f.write("".join(s.o))


def arc(cx, cy, r, a0, a1, rw):
    """Ring segment; angles in degrees, clockwise from 12 o'clock."""
    def p(rr, a):
        a = math.radians(a - 90)
        return cx + rr * math.cos(a), cy + rr * math.sin(a)
    large = 1 if a1 - a0 > 180 else 0
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = p(r, a0), p(r, a1), p(r - rw, a1), p(r - rw, a0)
    return (f"M{x0:.2f},{y0:.2f} A{r},{r} 0 {large} 1 {x1:.2f},{y1:.2f} L{x2:.2f},{y2:.2f} "
            f"A{r-rw},{r-rw} 0 {large} 0 {x3:.2f},{y3:.2f} Z")


def card_numbers(t):
    s = Svg(880, 72, t)
    cells = [(fmt(total), "contributions"), (fmt(this_year), f"in {today.year}"),
             (fmt(active), "active days"), (f"{longest}d", "longest streak"), (site.get("Rehber", "–"), "guides written")]
    cw = 878 / len(cells)
    s.r(1, 1, 878, 70, "none", f'stroke="{t["rule"]}"')
    for i, (n, l) in enumerate(cells):
        x = 1 + i * cw
        if i:
            s.ln(x, 1, x, 71, t["rule"])
        s.tx(x + 18, 36, n, t["link"] if i == 4 else t["text"], 20, weight=500, ls=-0.4)
        s.tx(x + 18, 54, l.upper(), t["faint"], 8, ls=1.2)
    return s


def card_clock(t):
    s = Svg(880, 330, t)
    cx, cy = 168, 166
    ys = sorted(per_year)
    ring = 100 / len(ys)
    mmax = max(month_tot.values()) or 1
    for yi, y in enumerate(ys):
        r = 40 + (yi + 1) * ring
        for mi in range(12):
            v = month_tot[f"{y}-{mi+1:02d}"]
            future = dt.date(y, mi + 1, 1) > today
            op = (0.15 + 0.85 * (v / mmax) ** 0.5) if v else 1
            col = t["link"] if v else (t["bg"] if future else t["cell"])
            s.o.append(f'<path d="{arc(cx, cy, r, mi*30+1, mi*30+29, ring-2)}" fill="{col}" fill-opacity="{op:.2f}"/>')
    for mi in range(12):
        a = math.radians(mi * 30 + 15 - 90)
        s.tx(cx + 152 * math.cos(a), cy + 152 * math.sin(a) + 3, TR_MON[mi][0], t["faint2"], 9, anchor="middle")
    s.tx(cx, cy - 2, fmt(total), t["text"], 18, anchor="middle", weight=500)
    s.tx(cx, cy + 14, f"{ys[0]}–{ys[-1]}", t["faint"], 8, anchor="middle", ls=1.2)
    s.label(360, 40, f"every month since {since}")
    s.tx(360, 58, f"one ring per year, {ys[0]} inside, {ys[-1]} outside. brighter = more.", t["faint2"], 10)
    ymax = max(sum(v) for v in per_year.values()) or 1
    for i, y in enumerate(reversed(ys)):
        yy = 96 + i * 34
        v = sum(per_year[y])
        cur = y == today.year
        s.tx(360, yy, y, t["faint"], 11)
        s.tx(420, yy, fmt(v), t["link"] if cur else t["text"], 16, weight=500)
        s.r(500, yy - 6, 300 * v / ymax, 3, t["link"] if cur else t["faint2"])
        pk = max(range(12), key=lambda m: month_tot[f"{y}-{m+1:02d}"])
        s.tx(880, yy, f"peak {TR_MON[pk]}", t["faint2"], 9, anchor="end")
        if i < len(ys) - 1:
            s.ln(360, yy + 13, 880, yy + 13, t["rule"])
    return s


def card_split(t):
    s = Svg(880, 230, t)
    pal = t["ramp"]

    def donut(cx, title, parts, center, sub):
        tot = sum(v for _, v in parts) or 1
        a0 = 0
        for i, (n, v) in enumerate(parts):
            a1 = a0 + 360 * v / tot
            if v:
                s.o.append(f'<path d="{arc(cx, 112, 70, a0 + 0.6, a1 - 0.6, 14)}" fill="{pal[min(i, len(pal)-1)]}"/>')
            a0 = a1
        s.tx(cx, 108, center, t["text"], 20, anchor="middle", weight=500)
        s.tx(cx, 124, sub, t["faint"], 8, anchor="middle", ls=1.2)
        s.label(cx, 14, title, anchor="middle")
        s.tx(cx, 212, "  ".join(f"{n} {round(100*v/tot)}%" for n, v in parts[:3]), t["faint2"], 9, anchor="middle")

    pub = sum(v[0] for v in per_year.values())
    pri = sum(v[1] for v in per_year.values())
    donut(150, "where", [("private", pri), ("public", pub)], fmt(total), "CONTRIBUTIONS")
    donut(440, "when", sorted(zip(wd_names, wd), key=lambda x: -x[1]), wd_names[wd.index(max(wd))].upper(), "BUSIEST DAY")
    if decks:
        top = sorted(decks, key=lambda x: -x[1])
        donut(730, "what I write", [(n.replace("-deck", ""), c) for n, c in top[:5]] + [("other", sum(c for _, c in top[5:]))],
              site.get("Rehber", "–"), "GUIDES")
    return s


def card_decks(t):
    s = Svg(880, 250, t)
    items = sorted(decks, key=lambda x: -x[1])

    def split(items, x, y, w, h):
        if len(items) == 1:
            return [(items[0], x, y, w, h)]
        tot = sum(v for _, v in items)
        acc, half = 0, []
        for it in items:
            if acc + it[1] > tot / 2 and half:
                break
            half.append(it)
            acc += it[1]
        rest = items[len(half):]
        if w >= h:
            w1 = w * acc / tot
            return split(half, x, y, w1, h) + split(rest, x + w1, y, w - w1, h)
        h1 = h * acc / tot
        return split(half, x, y, w, h1) + split(rest, x, y + h1, w, h - h1)

    s.label(0, 14, f"what I write · {site.get('Rehber', '–')} guides in {len(decks)} decks on x3beche.github.io")
    cmax = items[0][1]
    for (n, c), x, y, w, h in split(items, 0, 26, 880, 222):
        op = 0.18 + 0.7 * c / cmax
        s.r(x + 1, y + 1, w - 2, h - 2, t["link"], f'fill-opacity="{op:.2f}"')
        if w > 84 and h > 28:
            dark_ink = op > 0.6
            s.tx(x + 8, y + 18, n.replace("-deck", ""), t["bg"] if dark_ink else t["text"], 10, weight=500)
            s.tx(x + 8, y + 31, c, t["bg"] if dark_ink else t["faint"], 9)
    return s


CARDS = {"numbers": card_numbers, "clock": card_clock, "split": card_split}
if decks:
    CARDS["decks"] = card_decks
for theme, t in THEMES.items():
    for name, fn in CARDS.items():
        fn(t).save(os.path.join(OUT, f"card-{name}-{theme}.svg"))
print(f"total={total} year={this_year} active={active} longest={longest} decks={len(decks)} cards={list(CARDS)}")
