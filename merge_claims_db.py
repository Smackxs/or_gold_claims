#!/usr/bin/env python3
"""
Merge claims_OR.db, claims_CA.db, claims_ID.db and claims_NV.db into claims_slim.db
(the single file the app downloads). Same schema as before:
claims(_id, name, case_nr, claim_type, status, lat, lon), index on (lat, lon), android_metadata.

The four inputs hold disjoint case numbers (each starts with a different prefix), and _id is
BLM's OBJECTID (unique across the layer), so nothing needs de-duplicating.

Only Active claims are in the inputs. Refuses to produce a file if any prefix has fewer than
90% of the rows the server reported when it was pulled (stored in each input's meta table),
or is below a small floor, so a partial pull can never be published.
"""
import os, sqlite3, sys

PREFIXES = ["OR", "CA", "ID", "NV"]
FLOOR = {"OR": 5000, "CA": 1000, "ID": 1000, "NV": 100000}   # absolute minimums per prefix
MIN_RATIO = 0.90      # rows saved vs rows the server reported
MIN_TOTAL = 200000    # about 80% of the 253,782 Active claims expected on 2026-11-23
OUT = "claims_slim.db"


def main():
    for p in PREFIXES:
        if not os.path.exists(f"claims_{p}.db"):
            sys.exit(f"Missing claims_{p}.db - refusing to build a partial database")
    if os.path.exists(OUT):
        os.remove(OUT)
    db = sqlite3.connect(OUT)
    db.executescript("""
        CREATE TABLE claims (
            _id INTEGER PRIMARY KEY, name TEXT, case_nr TEXT,
            claim_type TEXT,   -- Placer / Lode
            status TEXT,       -- BLM disposition as reported
            lat REAL, lon REAL);
        CREATE TABLE android_metadata (locale TEXT);
        INSERT INTO android_metadata VALUES ('en_US');
    """)
    total = 0
    for p in PREFIXES:
        db.execute("ATTACH DATABASE ? AS src", (f"claims_{p}.db",))
        db.execute("""INSERT INTO claims
                      SELECT _id, name, case_nr, claim_type, status, lat, lon
                      FROM src.claims WHERE lat IS NOT NULL AND lon IS NOT NULL""")
        n = db.execute("SELECT COUNT(*) FROM src.claims").fetchone()[0]
        try:
            expected = db.execute("SELECT v FROM src.meta WHERE k='expected'").fetchone()[0]
        except Exception:
            sys.exit(f"claims_{p}.db has no 'expected' count - refusing to publish")
        db.commit()
        db.execute("DETACH DATABASE src")
        need = max(FLOOR[p], int(expected * MIN_RATIO))
        print(f"{p}: {n} rows (server reported {expected}; minimum {need})")
        if n < need:
            sys.exit(f"{p} has only {n} rows - refusing to publish a bad database")
        total += n
    n = db.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
    print(f"Merged total: {n} rows (minimum {MIN_TOTAL})")
    if n < MIN_TOTAL:
        sys.exit(f"Only {n} rows in total - refusing to publish a bad database")
    db.execute("CREATE INDEX idx_claims_lat_lon ON claims(lat, lon)")
    db.commit()
    print("Status counts:", db.execute("SELECT status, COUNT(*) FROM claims GROUP BY status").fetchall())
    db.execute("VACUUM")
    db.close()
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
