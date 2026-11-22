#!/usr/bin/env python3
"""
One step: download all ACTIVE placer + lode claims in Oregon from BLM MLRS and
write claims_slim.db with just: name, case_nr (BLM record number), lat, lon.

Usage: python build_claims_db.py        (Python 3.8+, no extra packages)
"""
import json, sqlite3, time, urllib.parse, urllib.request, os

LAYER = "https://nlsdbpubgis.blm.gov/arcgis/rest/services/Mining_Claims/MiningClaims/MapServer/1/query"
TYPES = "CSE_TYPE_NR IN ('384101','384103','384201','384203')"   # lode + placer
OR_ENV = "-124.75,41.95,-116.40,46.35"                           # Oregon bbox (WGS84)
PAGE = 500
OUT = "claims_slim.db"


def call(params, tries=5):
    data = urllib.parse.urlencode(params).encode()
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(LAYER, data=data), timeout=180) as r:
                out = json.load(r)
            if "error" in out:
                raise RuntimeError(out["error"])
            return out
        except Exception as e:
            print(f"  retry {i+1} ({e})"); time.sleep(2 ** i)
    raise SystemExit("Server kept failing - check your internet connection and try again.")


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


def main():
    if os.path.exists(OUT):
        os.remove(OUT)
    db = sqlite3.connect(OUT)
    db.executescript("""
        CREATE TABLE claims (_id INTEGER PRIMARY KEY, name TEXT, case_nr TEXT, lat REAL, lon REAL);
        CREATE TABLE android_metadata (locale TEXT);
        INSERT INTO android_metadata VALUES ('en_US');
    """)
    where = f"{TYPES}"
    total = call(spatial({"where": where, "returnCountOnly": "true", "f": "json"}))["count"]
    print(f"{total} claims found inside Oregon's bounding box")
    if total == 0:
        raise SystemExit("Server reported 0 claims - paste this output to Claude.")

    offset = 0
    while offset < total:
        data = call(spatial({"where": where, "outFields": "OBJECTID,CSE_NR,CSE_NAME,ADMIN_STATE,GEO_STATE",
                             "outSR": 4326, "returnGeometry": "true", "orderByFields": "OBJECTID",
                             "resultOffset": offset, "resultRecordCount": PAGE, "f": "geojson"}))
        feats = data.get("features", [])
        if not feats:
            break
        rows = []
        for f in feats:
            p, g = f["properties"], f.get("geometry")
            if not g or not g.get("coordinates"):
                continue
            lat, lon = center(g)
            rows.append((p.get("OBJECTID", f.get("id")), p.get("CSE_NAME"), p.get("CSE_NR"), lat, lon))
        db.executemany("INSERT OR REPLACE INTO claims VALUES (?,?,?,?,?)", rows)
        db.commit()
        offset += len(feats)
        print(f"  {offset}/{total}")

    db.execute("CREATE INDEX idx_claims_lat_lon ON claims(lat, lon)")
    n = db.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
    db.commit(); db.execute("VACUUM"); db.close()
    print(f"\nDone: {n} claims saved to {OUT}")
    print("Note: the bounding box also catches claims just across the OR border.")


if __name__ == "__main__":
    main()
