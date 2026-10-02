#!/usr/bin/env python3
"""Profile stats card: stats-dark.svg / stats-light.svg from GitHub GraphQL + x3beche.github.io.

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


def card(t):
    W, H = 880, 482
    o = []
    a = o.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
      f'font-family="\'IBM Plex Mono\',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace">')
    a(f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" fill="{t["bg"]}" stroke="{t["line"]}"/>')

    # KPI row
    kpis = [
        (fmt(total), "contributions", f"since {TR_MON[int(first[5:7])-1]} {first[:4]}"),
        (fmt(this_year), f"in {today.year}", f"{round(100*per_year[today.year][1]/max(this_year,1))}% in private repos"),
        (fmt(active), "active days", f"{active_year} in {today.year}"),
        (str(longest), "day longest streak", f"avg {total/active:.1f} per active day"),
        (str(busy_n), "busiest day", f"{TR_MON[int(busy_day[5:7])-1]} {int(busy_day[8:])}, {busy_day[:4]}"),
    ]
    cw = (W - 48) / len(kpis)
    for i, (n, l, s) in enumerate(kpis):
        x = 24 + i * cw
        if i:
            a(f'<line x1="{x:.1f}" y1="26" x2="{x:.1f}" y2="96" stroke="{t["line"]}"/>')
        a(f'<text x="{x+14:.1f}" y="58" font-size="28" font-weight="600" fill="{t["fg"]}">{escape(n)}</text>')
        a(f'<text x="{x+14:.1f}" y="78" font-size="12" fill="{t["accent"]}">{escape(l)}</text>')
        a(f'<text x="{x+14:.1f}" y="94" font-size="11" fill="{t["dim"]}">{escape(s)}</text>')
    a(f'<line x1="24" y1="116" x2="{W-24}" y2="116" stroke="{t["line"]}"/>')

    def label(x, y, s):
        a(f'<text x="{x}" y="{y}" font-size="11" letter-spacing="1" fill="{t["dim"]}">{escape(s)}</text>')

    # Yearly stacked bars (public / private)
    label(24, 142, "CONTRIBUTIONS PER YEAR")
    ys = sorted(per_year)
    ymax = max(sum(v) for v in per_year.values()) or 1
    bx, bw, base, hmax = 24, 46, 270, 100
    for i, y in enumerate(ys):
        pub, pri = per_year[y]
        x = bx + i * (bw + 18)
        hp, hr = hmax * pub / ymax, hmax * pri / ymax
        a(f'<rect x="{x}" y="{base-hp-hr:.1f}" width="{bw}" height="{hr:.1f}" fill="{t["accent2"]}"/>')
        a(f'<rect x="{x}" y="{base-hp:.1f}" width="{bw}" height="{hp:.1f}" fill="{t["accent"]}"/>')
        a(f'<text x="{x+bw/2}" y="{base-hp-hr-6:.1f}" font-size="11" text-anchor="middle" fill="{t["fg"]}">{fmt(pub+pri)}</text>')
        a(f'<text x="{x+bw/2}" y="{base+16}" font-size="11" text-anchor="middle" fill="{t["dim"]}">{y}</text>')
    lx = 24
    for col, s in ((t["accent"], "public repos"), (t["accent2"], "private repos")):
        a(f'<rect x="{lx}" y="300" width="9" height="9" fill="{col}"/>')
        a(f'<text x="{lx+14}" y="309" font-size="11" fill="{t["dim"]}">{s}</text>')
        lx += 124

    # Last 12 months
    label(470, 142, "LAST 12 MONTHS")
    mv = [month_tot[m.strftime("%Y-%m")] for m in months]
    mmax = max(mv) or 1
    mw = 28
    for i, (mm, v) in enumerate(zip(months, mv)):
        x = 470 + i * (mw + 4)
        h = max(hmax * v / mmax, 1 if v else 0)
        a(f'<rect x="{x}" y="{base-hmax}" width="{mw}" height="{hmax}" fill="{t["track"]}"/>')
        if h:
            a(f'<rect x="{x}" y="{base-h:.1f}" width="{mw}" height="{h:.1f}" fill="{t["accent"]}"/>')
        if v == max(mv) and v:
            a(f'<text x="{x+mw/2}" y="{base-h-6:.1f}" font-size="11" text-anchor="middle" fill="{t["fg"]}">{v}</text>')
        a(f'<text x="{x+mw/2}" y="{base+16}" font-size="10" text-anchor="middle" fill="{t["dim"]}">{TR_MON[mm.month-1][:1]}</text>')
    a(f'<line x1="24" y1="326" x2="{W-24}" y2="326" stroke="{t["line"]}"/>')

    # Weekday distribution
    label(24, 352, "BY WEEKDAY")
    wmax = max(wd) or 1
    for i, (n, v) in enumerate(zip(wd_names, wd)):
        y = 366 + i * 13
        a(f'<text x="24" y="{y+9}" font-size="10" fill="{t["dim"]}">{n}</text>')
        a(f'<rect x="58" y="{y}" width="{140*v/wmax:.1f}" height="9" fill="{t["accent"] if v == wmax else t["accent2"]}"/>')
        a(f'<text x="{64+140*v/wmax:.1f}" y="{y+9}" font-size="10" fill="{t["dim"]}">{v}</text>')

    # Top public repos
    label(262, 352, "TOP PUBLIC REPOS BY COMMITS")
    top = repos.most_common(6)
    rmax = top[0][1] if top else 1
    for i, (n, v) in enumerate(top):
        y = 366 + i * 15
        name = n if len(n) <= 24 else n[:23] + "…"
        a(f'<text x="262" y="{y+9}" font-size="11" fill="{t["fg"]}">{escape(name)}</text>')
        a(f'<rect x="440" y="{y+1}" width="{110*v/rmax:.1f}" height="8" fill="{t["accent"]}"/>')
        a(f'<text x="{446+110*v/rmax:.1f}" y="{y+9}" font-size="10" fill="{t["dim"]}">{v}</text>')

    # Knowledge base
    if site:
        label(620, 352, "X3BECHE.GITHUB.IO")
        rows = [(site.get("Deck"), "decks"), (site.get("Rehber"), "guides"),
                (site.get("Bölüm"), "sections"), (site.get("Kelime"), "words")]
        for i, (n, l) in enumerate(r for r in rows if r[0]):
            x, y = 620 + (i % 2) * 120, 386 + (i // 2) * 44
            a(f'<text x="{x}" y="{y}" font-size="22" font-weight="600" fill="{t["fg"]}">{escape(n)}</text>')
            a(f'<text x="{x}" y="{y+16}" font-size="11" fill="{t["accent"]}">{l}</text>')

    a(f'<text x="{W-24}" y="{H-12}" font-size="9" text-anchor="end" fill="{t["dim"]}">updated {today.isoformat()}</text>')
    a("</svg>")
    return "".join(o)


THEMES = {
    # colours of x3beche.github.io (assets/main.css)
    "dark": dict(bg="#0b0d10", line="#2a2f37", fg="#e6e8eb", dim="#8b9098", accent="#9ab6ff", accent2="#3a4766", track="#15191e"),
    "light": dict(bg="#ffffff", line="#d8dce1", fg="#1d2127", dim="#6b717a", accent="#3d63d6", accent2="#b9c7ef", track="#f1f3f6"),
}
for name, t in THEMES.items():
    with open(os.path.join(OUT, f"stats-{name}.svg"), "w") as f:
        f.write(card(t))
print(f"total={total} year={this_year} active={active} streak={current}/{longest} repos={len(repos)} site={site}")
