#!/usr/bin/env python3
"""
Golfigami scraper — runs via GitHub Actions every Monday.
Fetches latest PGA Tour results from ESPN and updates the database.
"""
import json, urllib.request, time
from pathlib import Path
from datetime import datetime

SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/golf/pga/scoreboard"
DATA_FILE  = Path("scorecards_data.json")
GNUM_FILE  = Path("golfigami_numbers.json")
HTML_FILE  = Path("index.html")

EXCLUDE = ['q-school', 'korn ferry', 'hero world', 'presidents cup', 'zurich classic']

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())

def is_excluded(name):
    return any(ex in name.lower() for ex in EXCLUDE)

def load_json(path, default):
    return json.loads(path.read_text()) if path.exists() else default

def next_gnum(gnum):
    return max((v["num"] for v in gnum.values()), default=0) + 1

def fetch_event(event_id, tourn_name, season):
    url = SCOREBOARD_URL + f"?event={event_id}"
    try:
        data = fetch(url)
        competitors = data["events"][0]["competitions"][0]["competitors"]
        scorecards = []
        for comp in competitors:
            name = comp.get("athlete", {}).get("fullName", "Unknown")
            rounds = {}
            for ls in comp.get("linescores", []):
                p = ls.get("period")
                v = ls.get("value")
                if p in (1,2,3,4) and v is not None:
                    try: rounds[p] = int(float(v))
                    except: pass
            if len(rounds) == 4:
                scorecards.append({"name": name, "tournament": tourn_name,
                                   "season": season,
                                   "r1": rounds[1], "r2": rounds[2],
                                   "r3": rounds[3], "r4": rounds[4]})
        return scorecards
    except Exception as e:
        print(f"  Error: {e}")
        return []

def merge(data, gnum, scorecards, season):
    added = new_g = 0
    counter = next_gnum(gnum)
    for sc in scorecards:
        key   = f"{sc['r1']}-{sc['r2']}-{sc['r3']}-{sc['r4']}"
        entry = [sc["name"], sc["tournament"][:40], sc["season"]]
        if key not in gnum:
            gnum[key] = {"num": counter, "fp": sc["name"],
                         "ft": sc["tournament"], "fs": sc["season"]}
            counter += 1; new_g += 1
        if key not in data:
            data[key] = [1, entry]; added += 1
        else:
            if not any(e[0]==sc["name"] and e[2]==season for e in data[key][1:]):
                data[key][0] += 1
                data[key].insert(1, entry); added += 1
    print(f"  +{added} entries, +{new_g} new Golfigamis")
    return data, gnum

def build_site_data(data, gnum, latest_name, latest_season, latest_scorecards):
    scorecards = {}
    for k, v in data.items():
        count = v[0]; examples = v[1:]
        mr = examples[0] if examples else ["","",""]
        g  = gnum.get(k, {})
        scorecards[k] = {
            "c": count, "mr": mr[2], "mrn": mr[0], "mrt": mr[1],
            "e": examples[:5],
            "gn": g.get("num",0), "fp": g.get("fp",""),
            "ft": g.get("ft","")[:40], "fs": g.get("fs",""),
        }
    players = []
    for sc in latest_scorecards:
        key = f"{sc['r1']}-{sc['r2']}-{sc['r3']}-{sc['r4']}"
        g   = gnum.get(key, {})
        players.append({
            "n": sc["name"], "k": key,
            "r1": sc["r1"], "r2": sc["r2"], "r3": sc["r3"], "r4": sc["r4"],
            "t": sc["r1"]+sc["r2"]+sc["r3"]+sc["r4"],
            "c": data.get(key,[1])[0], "gn": g.get("num",0),
        })
    players.sort(key=lambda p: p["t"])
    return {"scorecards": scorecards,
            "latest": {"name": latest_name, "season": latest_season, "players": players}}

def rebuild_html(site_data):
    SC   = site_data["scorecards"]
    lat  = site_data["latest"]
    totalSC  = sum(v["c"] for v in SC.values())
    maxGN    = max((v["gn"] for v in SC.values()), default=0)
    data_json = json.dumps(site_data, separators=(",",":"))

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Golfigami</title>
<meta name="description" content="Has that 4-round scorecard ever been shot on the PGA Tour?">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f5f5f0;min-height:100vh;display:flex;align-items:flex-start;justify-content:center;padding:2rem 1rem}}
.wrap{{width:100%;max-width:660px;display:flex;flex-direction:column;gap:1.25rem}}
.card{{background:white;border-radius:16px;padding:1.75rem;box-shadow:0 1px 3px rgba(0,0,0,.07)}}
h1{{font-size:22px;font-weight:600;color:#1a1a1a;margin-bottom:3px}}
.sub{{font-size:13px;color:#888;margin-bottom:1.5rem}}
h2{{font-size:15px;font-weight:600;color:#1a1a1a;margin-bottom:1rem}}
.input-row{{display:flex;gap:10px;align-items:flex-end;flex-wrap:wrap;margin-bottom:1.25rem}}
.score-group{{display:flex;flex-direction:column;gap:5px}}
.score-group label{{font-size:11px;color:#888;font-weight:600;letter-spacing:.06em}}
.score-group input{{width:66px;text-align:center;font-size:22px;font-weight:500;color:#1a1a1a;border:1.5px solid #e0e0e0;border-radius:10px;padding:9px 6px;outline:none;transition:border-color .15s}}
.score-group input:focus{{border-color:#3b6d11}}
.dash{{font-size:20px;color:#ccc;padding-bottom:9px}}
button.primary{{height:46px;padding:0 1.25rem;font-size:15px;font-weight:500;background:#3b6d11;color:white;border:none;border-radius:10px;cursor:pointer;transition:background .15s;align-self:flex-end}}
button.primary:hover{{background:#27500a}}
.banner{{border-radius:12px;padding:1.1rem 1.35rem;margin-bottom:.85rem}}
.banner.golfigami{{background:#eaf3de;border:1px solid #c0dd97}}
.banner.seen{{background:#fcebeb;border:1px solid #f7c1c1}}
.banner-title{{font-size:17px;font-weight:600;margin-bottom:3px}}
.golfigami .banner-title{{color:#27500a}}
.seen .banner-title{{color:#791f1f}}
.banner-sub{{font-size:13px;line-height:1.6}}
.golfigami .banner-sub{{color:#3b6d11;opacity:.9}}
.seen .banner-sub{{color:#a32d2d;opacity:.9}}
.list{{background:#fafafa;border:1px solid #ebebeb;border-radius:12px;overflow:hidden}}
.list-header{{font-size:11px;font-weight:600;color:#888;letter-spacing:.06em;padding:10px 14px;border-bottom:1px solid #ebebeb;background:white;display:flex;justify-content:space-between;align-items:center}}
.list-header span{{font-weight:400;font-size:11px;color:#bbb;letter-spacing:0}}
.row{{display:flex;justify-content:space-between;align-items:center;padding:10px 14px;border-bottom:1px solid #f0f0f0;cursor:pointer;transition:background .1s;gap:12px}}
.row:last-child{{border-bottom:none}}
.row:hover{{background:#f5f5f0}}
.row-left{{display:flex;flex-direction:column;gap:2px;min-width:0}}
.player{{font-size:14px;font-weight:500;color:#1a1a1a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.rounds{{font-size:12px;color:#888;font-variant-numeric:tabular-nums}}
.row-right{{display:flex;flex-direction:column;align-items:flex-end;gap:4px;flex-shrink:0}}
.badge{{display:inline-block;font-size:11px;font-weight:600;padding:2px 8px;border-radius:20px;white-space:nowrap}}
.badge.new{{background:#eaf3de;color:#27500a}}
.badge.rare{{background:#faeeda;color:#633806}}
.badge.common{{background:#f0f0f0;color:#666}}
.static-row{{cursor:default!important}}
.static-row:hover{{background:white!important}}
.more{{font-size:12px;color:#aaa;padding:9px 14px}}
.meta{{font-size:12px;color:#aaa}}
.year-tag{{font-size:12px;font-weight:500;color:#1a1a1a}}
</style>
</head>
<body>
<div class="wrap">
  <div class="card">
    <h1>⛳ Golfigami</h1>
    <p class="sub">PGA Tour 2001–2026 · {totalSC:,} scorecards · {len(SC):,} unique sequences · Golfigami #{maxGN:,} discovered</p>
    <div class="input-row">
      <div class="score-group"><label>ROUND 1</label><input type="number" id="r1" min="55" max="95" placeholder="68"></div>
      <span class="dash">–</span>
      <div class="score-group"><label>ROUND 2</label><input type="number" id="r2" min="55" max="95" placeholder="70"></div>
      <span class="dash">–</span>
      <div class="score-group"><label>ROUND 3</label><input type="number" id="r3" min="55" max="95" placeholder="65"></div>
      <span class="dash">–</span>
      <div class="score-group"><label>ROUND 4</label><input type="number" id="r4" min="55" max="95" placeholder="67"></div>
      <button class="primary" onclick="lookup()">Look up</button>
    </div>
    <div id="result"></div>
  </div>
  <div class="card">
    <h2>{lat['name']} {lat['season']}</h2>
    <div class="list" id="recent-list"></div>
  </div>
</div>
<script>
const DB={data_json};
const SC=DB.scorecards;
const lat=DB.latest;
const maxGN=Math.max(...Object.values(SC).map(v=>v.gn));
function badge(p){{
  if(p.c===1)return`<span class="badge new">Golfigami #${{p.gn.toLocaleString()}}</span>`;
  if(p.c<=5)return`<span class="badge rare">Rare · ${{p.c}}x</span>`;
  return`<span class="badge common">${{p.c}}x</span>`;
}}
function renderRecent(){{
  const rows=lat.players.map(p=>{{
    const pts=p.k.split('-');
    return`<div class="row" onclick="fillLookup('${{pts[0]}}','${{pts[1]}}','${{pts[2]}}','${{pts[3]}}')">
      <span class="row-left"><span class="player">${{p.n}}</span><span class="rounds">${{p.k.replace(/-/g,'–')}} · ${{p.t}} total</span></span>
      <span class="row-right">${{badge(p)}}</span></div>`;
  }}).join('');
  document.getElementById('recent-list').innerHTML=
    `<div class="list-header">PLAYERS — sorted by score <span>click to look up</span></div>`+rows;
}}
function fillLookup(r1,r2,r3,r4){{
  document.getElementById('r1').value=r1;
  document.getElementById('r2').value=r2;
  document.getElementById('r3').value=r3;
  document.getElementById('r4').value=r4;
  lookup();window.scrollTo({{top:0,behavior:'smooth'}});
}}
function lookup(){{
  const r1=document.getElementById('r1').value.trim();
  const r2=document.getElementById('r2').value.trim();
  const r3=document.getElementById('r3').value.trim();
  const r4=document.getElementById('r4').value.trim();
  const out=document.getElementById('result');
  if(!r1||!r2||!r3||!r4){{out.innerHTML='<p style="color:#a32d2d;font-size:14px;padding:4px 0">Please enter all four scores.</p>';return;}}
  const key=r1+'-'+r2+'-'+r3+'-'+r4;
  const total=parseInt(r1)+parseInt(r2)+parseInt(r3)+parseInt(r4);
  const match=SC[key];
  if(!match){{
    out.innerHTML=`<div class="banner golfigami"><div class="banner-title">🎉 Golfigami!</div><div class="banner-sub">${{r1}}–${{r2}}–${{r3}}–${{r4}} (${{total}} total) has never been shot in a PGA Tour event.<br>This would be <strong>Golfigami #${{(maxGN+1).toLocaleString()}}</strong>.</div></div>`;
  }}else{{
    const count=match.c;const examples=match.e;
    const rows=examples.map(e=>`<div class="row static-row"><span class="row-left"><span class="player">${{e[0]}}</span><span class="meta">${{e[1]}}</span></span><span class="row-right"><span class="year-tag">${{e[2]}}</span></span></div>`).join('');
    const more=count>examples.length?`<div class="more">+ ${{count-examples.length}} more not shown</div>`:'';
    const first=match.fp?`First shot by <strong>${{match.fp}}</strong> at ${{match.ft}} (${{match.fs}}).`:'';
    out.innerHTML=`<div class="banner seen"><div class="banner-title">Golfigami #${{match.gn.toLocaleString()}}</div><div class="banner-sub">${{r1}}–${{r2}}–${{r3}}–${{r4}} (${{total}} total) has been shot <strong>${{count}}×</strong> on tour. Most recently by <strong>${{match.mrn}}</strong> (${{match.mr}}).<br>${{first}}</div></div><div class="list"><div class="list-header">WHO'S SHOT IT <span>most recent first</span></div>${{rows}}${{more}}</div>`;
  }}
}}
document.addEventListener('keydown',e=>{{if(e.key==='Enter')lookup();}});
renderRecent();
</script>
</body>
</html>"""
    HTML_FILE.write_text(html)
    print(f"index.html rebuilt ({len(html)//1024} KB)")

def main():
    data = load_json(DATA_FILE, {})
    gnum = load_json(GNUM_FILE, {})
    print(f"Loaded {len(data)} combos, {len(gnum)} Golfigami numbers")

    espn = fetch(SCOREBOARD_URL)
    events     = espn.get("events", [])
    calendar   = espn.get("leagues", [{}])[0].get("calendar", [])

    if not events:
        print("No current event found.")
        return

    event       = events[0]
    tourn_name  = event.get("name", "Unknown")
    season      = str(event.get("season", {}).get("year", datetime.now().year))
    competitors = event.get("competitions", [{}])[0].get("competitors", [])

    if is_excluded(tourn_name):
        print(f"Skipping excluded event: {tourn_name}")
        return

    print(f"Event: {tourn_name} ({season}) — {len(competitors)} players")

    scorecards = []
    for comp in competitors:
        name   = comp.get("athlete", {}).get("fullName", "Unknown")
        rounds = {}
        for ls in comp.get("linescores", []):
            p = ls.get("period"); v = ls.get("value")
            if p in (1,2,3,4) and v is not None:
                try: rounds[p] = int(float(v))
                except: pass
        if len(rounds) == 4:
            scorecards.append({"name": name, "tournament": tourn_name,
                               "season": season,
                               "r1": rounds[1], "r2": rounds[2],
                               "r3": rounds[3], "r4": rounds[4]})

    print(f"Complete 4-round scorecards: {len(scorecards)}")
    if not scorecards:
        print("Tournament may still be in progress.")
        return

    data, gnum = merge(data, gnum, scorecards, season)

    DATA_FILE.write_text(json.dumps(data, separators=(",",":")))
    GNUM_FILE.write_text(json.dumps(gnum, separators=(",",":")))
    print("Data saved.")

    site_data = build_site_data(data, gnum, tourn_name, season, scorecards)
    rebuild_html(site_data)
    print("Done!")

if __name__ == "__main__":
    main()
