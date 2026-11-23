#!/usr/bin/env python3
"""
Download all placer + lode claims whose BLM case number starts with 'OR' from MLRS and write
claims_slim.db: name, case_nr (BLM record number), claim_type, status, lat, lon.

Resumable: progress is saved after every page, so if the BLM server errors out
and the script is run again (or retried by the workflow), it continues where it stopped.

Usage: python -u build_claims_db.py          (resumes an unfinished download)
       python -u build_claims_db.py --fresh  (start over)
"""
import json, sqlite3, sys, time, urllib.parse, urllib.request, os

LAYER = "https://nlsdbpubgis.blm.gov/arcgis/rest/services/Mining_Claims/MiningClaims/MapServer/1/query"
TYPES = "CSE_TYPE_NR IN ('384101','384103','384201','384203')"   # lode + placer
WHERE_BASE = f"({TYPES}) AND CSE_NR LIKE 'OR%'"                         # Oregon case numbers only
LABELS = {"384101": "Lode", "384103": "Lode", "384201": "Placer", "384203": "Placer"}
OR_ENV = "-124.75,41.95,-116.40,46.35"                           # Oregon bbox (WGS84)
PAGE_MAX, PAGE_MIN = 500, 50
MAX_FAILS = 8
OUT = "claims_slim.db"


def log(*a):
    print(*a, flush=True)


def call(params, tries=3):
    data = urllib.parse.urlencode(params).encode()
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(LAYER, data=data), timeout=180) as r:
                out = json.load(r)
            if "error" in out:
                raise RuntimeError(out["error"])
            return out
        except Exception as e:
            last = e
            log(f"  request failed ({e}); retry {i+1}/{tries}")
            time.sleep(5 * 2 ** i)
    raise RuntimeError(last)


def spatial(p):
    p.update(geometry=OR_ENV, geometryType="esriGeometryEnvelope", inSR=4326,
             spatialRel="esriSpatialRelIntersects")
    return p


def center(g):
    xs, ys = [], []
    def walk(c):
        if isinstance(c[0], (int, float)): xs.append(c[0]); ys.append(c[1])
        else:
            for s in c: walk(s)
    walk(g["coordinates"])
    return (min(ys) + max(ys)) / 2, (min(xs) + max(xs)) / 2


def open_db(fresh):
    if fresh and os.path.exists(OUT):
        os.remove(OUT)
    db = sqlite3.connect(OUT)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS claims (
            _id INTEGER PRIMARY KEY, name TEXT, case_nr TEXT,
            claim_type TEXT,   -- Placer / Lode
            status TEXT,       -- BLM disposition as reported: Active, Filed, Under Review, On Appeal, Interim
            lat REAL, lon REAL);
        CREATE TABLE IF NOT EXISTS android_metadata (locale TEXT);
        CREATE TABLE IF NOT EXISTS progress (k TEXT PRIMARY KEY, v INTEGER);
    """)
    if not db.execute("SELECT COUNT(*) FROM android_metadata").fetchone()[0]:
        db.execute("INSERT INTO android_metadata VALUES ('en_US')")
    done = db.execute("SELECT v FROM progress WHERE k='done'").fetchone()
    if done and done[0] == 1:          # previous run finished -> start over
        db.close(); os.remove(OUT)
        return open_db(False)
    db.commit()
    return db


def main():
    db = open_db("--fresh" in sys.argv)
    row = db.execute("SELECT v FROM progress WHERE k='last_oid'").fetchone()
    last_oid = row[0] if row else 0
    if last_oid:
        log(f"Resuming after OBJECTID {last_oid} ({db.execute('SELECT COUNT(*) FROM claims').fetchone()[0]} claims already saved)")

    total = call(spatial({"where": WHERE_BASE, "returnCountOnly": "true", "f": "json"}), tries=5)["count"]
    log(f"{total} claims with an OR case number found")
    if total == 0:
        raise SystemExit("Server reported 0 claims - paste this output to Claude.")

    page, fails, scanned = PAGE_MAX, 0, 0
    while True:
        try:
            data = call(spatial({
                "where": f"{WHERE_BASE} AND OBJECTID > {last_oid}",
                "outFields": "OBJECTID,CSE_NR,CSE_NAME,CSE_TYPE_NR,BLM_PROD,CSE_DISP",
                "outSR": 4326, "returnGeometry": "true", "orderByFields": "OBJECTID",
                "resultRecordCount": page, "f": "geojson"}))
        except Exception as e:
            fails += 1
            page = max(PAGE_MIN, page // 2)
            if fails >= MAX_FAILS:
                log(f"Giving up after {fails} consecutive failures. Progress is saved; run again to resume.")
                raise SystemExit(1)
            wait = min(30 * fails, 180)
            log(f"  server trouble ({e}); page size now {page}, waiting {wait}s (failure {fails}/{MAX_FAILS})")
            time.sleep(wait)
            continue
        fails = 0
        feats = data.get("features", [])
        if not feats:
            break
        rows, max_oid = [], last_oid
        for f in feats:
            p, g = f["properties"], f.get("geometry")
            oid = p.get("OBJECTID", f.get("id"))
            max_oid = max(max_oid, oid)
            if not g or not g.get("coordinates"):
                continue
            if not (p.get("CSE_NR") or "").startswith("OR"):   # safety net: Oregon case numbers only
                continue
            lat, lon = center(g)
            rows.append((oid, p.get("CSE_NAME"), p.get("CSE_NR"),
                         LABELS.get(p.get("CSE_TYPE_NR"), p.get("BLM_PROD")), p.get("CSE_DISP"), lat, lon))
        db.executemany("INSERT OR REPLACE INTO claims VALUES (?,?,?,?,?,?,?)", rows)
        last_oid = max_oid
        db.execute("INSERT OR REPLACE INTO progress VALUES ('last_oid', ?)", (last_oid,))
        db.commit()
        saved = db.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
        log(f"  {saved} saved (of about {total})")
        page = min(PAGE_MAX, page * 2)
        time.sleep(0.5)

    db.execute("CREATE INDEX IF NOT EXISTS idx_claims_lat_lon ON claims(lat, lon)")
    db.execute("INSERT OR REPLACE INTO progress VALUES ('done', 1)")
    n = db.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
    log("Status counts:", db.execute("SELECT status, COUNT(*) FROM claims GROUP BY status").fetchall())
    log("Type counts:  ", db.execute("SELECT claim_type, COUNT(*) FROM claims GROUP BY claim_type").fetchall())
    db.commit()
    db.execute("DROP TABLE progress"); db.commit(); db.execute("VACUUM"); db.close()
    log(f"\nDone: {n} claims saved to {OUT}")


if __name__ == "__main__":
    main()
