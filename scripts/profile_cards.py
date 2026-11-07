#!/usr/bin/env python3
"""Render burgundy contribution-heatmap and statistics cards from real GitHub data.

Runs inside the "Generate profile assets" workflow. It reads the public
contribution calendar and public, non-fork repositories through the GitHub
GraphQL API and writes two SVG files. Nothing is estimated: if the API call
fails, the script exits non-zero and the previously published cards stay up.

    GITHUB_TOKEN=... python3 scripts/profile_cards.py --user itsluckysharma01 --out dist

The token is read from the environment only and is never written to output.

For a local layout check without network access, use --demo. Demo output is
stamped "DEMO DATA — NOT REAL" across the card and must not be published.
"""
import argparse
import datetime as dt
import json
import os
import random
import sys
import urllib.request
from xml.sax.saxutils import escape

API = "https://api.github.com/graphql"

QUERY = """
query($login: String!, $cursor: String) {
  user(login: $login) {
    followers { totalCount }
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount contributionLevel } }
      }
    }
    repositories(first: 100, after: $cursor, ownerAffiliations: OWNER,
                 isFork: false, privacy: PUBLIC) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
  }
}
"""

# Palette
MIDNIGHT, WINE, BURGUNDY, ACCENT = "#10070C", "#190B12", "#451126", "#701A3D"
ROSE, PALE, IVORY = "#C77B9B", "#E5B5C7", "#F8F0F3"
LEVELS = {
    "NONE": "#24111B",
    "FIRST_QUARTILE": BURGUNDY,
    "SECOND_QUARTILE": ACCENT,
    "THIRD_QUARTILE": ROSE,
    "FOURTH_QUARTILE": PALE,
}
LANG_COLORS = [PALE, ROSE, "#A34A72", ACCENT, BURGUNDY, "#3A1A28"]
SERIF = "'Cormorant Garamond','Playfair Display','Iowan Old Style','Palatino Linotype',Palatino,Georgia,serif"
MONO = "'JetBrains Mono','SFMono-Regular',Menlo,Consolas,'Liberation Mono',monospace"


# ---------------------------------------------------------------- data

def gql(token, variables):
    body = json.dumps({"query": QUERY, "variables": variables}).encode()
    req = urllib.request.Request(API, data=body, headers={
        "Authorization": f"bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "profile-cards-workflow",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if payload.get("errors"):
        raise RuntimeError(f"GraphQL errors: {payload['errors']}")
    if not payload.get("data", {}).get("user"):
        raise RuntimeError("User not found or no data returned")
    return payload["data"]["user"]


def fetch(user, token):
    first = gql(token, {"login": user, "cursor": None})
    repos = list(first["repositories"]["nodes"])
    page = first["repositories"]["pageInfo"]
    while page["hasNextPage"]:
        nxt = gql(token, {"login": user, "cursor": page["endCursor"]})
        repos += nxt["repositories"]["nodes"]
        page = nxt["repositories"]["pageInfo"]

    cal = first["contributionsCollection"]["contributionCalendar"]
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]
    langs = {}
    for r in repos:
        for e in r["languages"]["edges"]:
            langs[e["node"]["name"]] = langs.get(e["node"]["name"], 0) + e["size"]
    return {
        "weeks": cal["weeks"],
        "days": days,
        "total": cal["totalContributions"],
        "followers": first["followers"]["totalCount"],
        "repos": first["repositories"]["totalCount"],
        "stars": sum(r["stargazerCount"] for r in repos),
        "languages": langs,
        "demo": False,
    }


def demo_data():
    rng = random.Random(7)
    start = dt.date.today() - dt.timedelta(days=364)
    start -= dt.timedelta(days=(start.weekday() + 1) % 7)
    weeks, day = [], start
    lv = ["NONE", "FIRST_QUARTILE", "SECOND_QUARTILE", "THIRD_QUARTILE", "FOURTH_QUARTILE"]
    while day <= dt.date.today():
        w = []
        for _ in range(7):
            if day > dt.date.today():
                break
            c = rng.choice([0, 0, 1, 2, 4, 7])
            w.append({"date": day.isoformat(), "contributionCount": c,
                      "contributionLevel": lv[min(4, (c + 1) // 2)]})
            day += dt.timedelta(days=1)
        weeks.append({"contributionDays": w})
    days = [d for w in weeks for d in w["contributionDays"]]
    return {"weeks": weeks, "days": days, "total": sum(d["contributionCount"] for d in days),
            "followers": 0, "repos": 0, "stars": 0,
            "languages": {"Language A": 50, "Language B": 30, "Language C": 20}, "demo": True}


def streaks(days):
    counts = [d["contributionCount"] for d in days]
    longest = run = 0
    for c in counts:
        run = run + 1 if c else 0
        longest = max(longest, run)
    current, i = 0, len(counts) - 1
    if i >= 0 and counts[i] == 0:  # today not counted yet: start from yesterday
        i -= 1
    while i >= 0 and counts[i]:
        current += 1
        i -= 1
    return current, longest


# ---------------------------------------------------------------- svg helpers

def card(w, h, uid, body, title, demo):
    stamp = ""
    if demo:
        stamp = (f'<text x="{w/2}" y="{h/2 + 10}" text-anchor="middle" font-family="{MONO}" font-size="30" '
                 f'font-weight="700" letter-spacing="6" fill="{IVORY}" fill-opacity="0.85" '
                 f'transform="rotate(-8 {w/2} {h/2})">DEMO DATA — NOT REAL</text>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-labelledby="{uid}-title">
  <title id="{uid}-title">{escape(title)}</title>
  <defs>
    <linearGradient id="{uid}-bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{MIDNIGHT}"/><stop offset="1" stop-color="{WINE}"/>
    </linearGradient>
    <clipPath id="{uid}-clip"><rect width="{w}" height="{h}" rx="18"/></clipPath>
  </defs>
  <g clip-path="url(#{uid}-clip)">
    <rect width="{w}" height="{h}" fill="url(#{uid}-bg)"/>
{body}
    <rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="18" fill="none" stroke="{ACCENT}" stroke-opacity="0.8"/>
    {stamp}
  </g>
</svg>
'''


def header(x, y, kicker, heading):
    return (f'    <text x="{x}" y="{y}" font-family="{MONO}" font-size="11" letter-spacing="3" fill="{ROSE}">{escape(kicker)}</text>\n'
            f'    <text x="{x}" y="{y + 32}" font-family="{SERIF}" font-size="26" font-style="italic" fill="{IVORY}">{escape(heading)}</text>\n')


# ---------------------------------------------------------------- cards

def heatmap(data, updated):
    uid = "lsh-heat"
    cell, gap = 13, 3
    step = cell + gap
    left, top = 64, 104
    weeks = data["weeks"]
    w = left + len(weeks) * step + 40
    h = top + 7 * step + 64
    out = [header(40, 46, f"CONTRIBUTIONS · LAST 12 MONTHS · UPDATED {updated}",
                  f"{data['total']:,} contributions in the last year")]

    # day labels
    for row, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        out.append(f'    <text x="{left - 12}" y="{top + row * step + cell - 2}" text-anchor="end" font-family="{MONO}" font-size="10" fill="{ROSE}" fill-opacity="0.7">{name}</text>')

    # month labels + cells
    last_month = None
    for wi, wk in enumerate(weeks):
        x = left + wi * step
        if wk["contributionDays"]:
            first = dt.date.fromisoformat(wk["contributionDays"][0]["date"])
            if first.month != last_month and first.day <= 7 and wi < len(weeks) - 2:
                out.append(f'    <text x="{x}" y="{top - 10}" font-family="{MONO}" font-size="10" fill="{ROSE}" fill-opacity="0.8">{first.strftime("%b")}</text>')
                last_month = first.month
        for d in wk["contributionDays"]:
            row = (dt.date.fromisoformat(d["date"]).weekday() + 1) % 7  # Sunday first, like GitHub
            fill = LEVELS.get(d["contributionLevel"], LEVELS["NONE"])
            n = d["contributionCount"]
            out.append(f'    <rect x="{x}" y="{top + row * step}" width="{cell}" height="{cell}" rx="3" fill="{fill}">'
                       f'<title>{d["date"]}: {n} contribution{"s" if n != 1 else ""}</title></rect>')

    # slow scanning column (decorative, data-independent)
    gw = len(weeks) * step
    out.append(f'    <rect x="{left - step}" y="{top - 4}" width="{step}" height="{7 * step + 4}" rx="3" fill="{IVORY}" opacity="0.05">'
               f'<animate attributeName="x" values="{left - step};{left + gw}" dur="14s" repeatCount="indefinite"/></rect>')

    # legend
    ly = top + 7 * step + 30
    lx = w - 40 - 5 * step - 70
    out.append(f'    <text x="{lx}" y="{ly + 10}" font-family="{MONO}" font-size="10" fill="{ROSE}" fill-opacity="0.8">Less</text>')
    for i, k in enumerate(LEVELS):
        out.append(f'    <rect x="{lx + 34 + i * step}" y="{ly}" width="{cell}" height="{cell}" rx="3" fill="{LEVELS[k]}"/>')
    out.append(f'    <text x="{lx + 40 + 5 * step}" y="{ly + 10}" font-family="{MONO}" font-size="10" fill="{ROSE}" fill-opacity="0.8">More</text>')
    out.append(f'    <text x="40" y="{ly + 10}" font-family="{MONO}" font-size="10" fill="{IVORY}" fill-opacity="0.45">Source: GitHub GraphQL contribution calendar</text>')

    return card(w, h, uid, "\n".join(out), f"GitHub contributions for the last year: {data['total']}", data["demo"])


def stats(data, updated):
    uid = "lsh-stats"
    w, h = 960, 300
    cur, longest = streaks(data["days"])
    metrics = [
        ("CONTRIBUTIONS", f"{data['total']:,}", "last 12 months"),
        ("CURRENT STREAK", f"{cur}", "days"),
        ("LONGEST STREAK", f"{longest}", "days, last 12 months"),
        ("PUBLIC REPOS", f"{data['repos']}", "original, non-fork"),
        ("STARS", f"{data['stars']}", "on those repos"),
        ("FOLLOWERS", f"{data['followers']}", "on GitHub"),
    ]
    out = [header(40, 46, f"GITHUB · UPDATED {updated}", "At a glance")]
    col = (w - 80) / len(metrics)
    for i, (k, v, sub) in enumerate(metrics):
        x = 40 + i * col
        if i:
            out.append(f'    <rect x="{x - 14}" y="104" width="1" height="64" fill="{ACCENT}" opacity="0.8"/>')
        out.append(f'    <text x="{x}" y="116" font-family="{MONO}" font-size="9.5" letter-spacing="2" fill="{ROSE}">{k}</text>')
        out.append(f'    <text x="{x}" y="152" font-family="{SERIF}" font-size="34" font-weight="600" fill="{IVORY}">{escape(v)}</text>')
        out.append(f'    <text x="{x}" y="170" font-family="{MONO}" font-size="9.5" fill="{IVORY}" fill-opacity="0.5">{escape(sub)}</text>')

    # language bar
    langs = sorted(data["languages"].items(), key=lambda kv: kv[1], reverse=True)
    total = sum(v for _, v in langs) or 1
    top6 = langs[:5]
    rest = sum(v for _, v in langs[5:])
    if rest:
        top6.append(("Other", rest))
    bx, by, bw = 40, 214, w - 80
    out.append(f'    <text x="{bx}" y="{by - 12}" font-family="{MONO}" font-size="9.5" letter-spacing="2" fill="{ROSE}">LANGUAGES · BY CODE SIZE ACROSS PUBLIC NON-FORK REPOS</text>')
    x = bx
    legend_x = bx
    for i, (name, size) in enumerate(top6):
        frac = size / total
        seg = bw * frac
        color = LANG_COLORS[i % len(LANG_COLORS)]
        out.append(f'    <rect x="{x:.1f}" y="{by}" width="{max(seg - 2, 1):.1f}" height="10" rx="2" fill="{color}"/>')
        x += seg
        label = f"{name} {frac * 100:.1f}%"
        out.append(f'    <rect x="{legend_x}" y="{by + 30}" width="8" height="8" rx="2" fill="{color}"/>')
        out.append(f'    <text x="{legend_x + 14}" y="{by + 38}" font-family="{MONO}" font-size="10.5" fill="{IVORY}" fill-opacity="0.8">{escape(label)}</text>')
        legend_x += 14 + len(label) * 6.6 + 22
    if not langs:
        out.append(f'    <text x="{bx}" y="{by + 10}" font-family="{MONO}" font-size="10.5" fill="{IVORY}" fill-opacity="0.6">No language data on public repositories yet.</text>')

    return card(w, h, uid, "\n".join(out), "GitHub statistics for itsluckysharma01", data["demo"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="itsluckysharma01")
    ap.add_argument("--out", default="dist")
    ap.add_argument("--demo", action="store_true", help="synthetic, clearly stamped data for layout checks")
    a = ap.parse_args()

    if a.demo:
        data = demo_data()
    else:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            sys.exit("GITHUB_TOKEN is not set")
        data = fetch(a.user, token)

    updated = dt.datetime.now(dt.timezone.utc).strftime("%d %b %Y").upper()
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "lucky-heatmap.svg"), "w", encoding="utf-8") as f:
        f.write(heatmap(data, updated))
    with open(os.path.join(a.out, "lucky-stats.svg"), "w", encoding="utf-8") as f:
        f.write(stats(data, updated))
    print(f"wrote cards for {a.user}: {data['total']} contributions, {data['repos']} repos"
          + (" (DEMO)" if data["demo"] else ""))


if __name__ == "__main__":
    main()
