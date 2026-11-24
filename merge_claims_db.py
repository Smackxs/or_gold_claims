#!/usr/bin/env python3
"""
Merge claims_OR.db, claims_CA.db, claims_ID.db and claims_NV.db into claims_slim.db
(the single file the app downloads). Same schema as before:
claims(_id, name, case_nr, claim_type, status, lat, lon), index on (lat, lon), android_metadata.

The four inputs hold disjoint case numbers (each starts with a different prefix), and _id is
BLM's OBJECTID (unique across the layer), so nothing needs de-duplicating.

Refuses to produce a file if any prefix is suspiciously small, so a partial pull can never
be published. Minimums are about 80% of the counts BLM reported on 2026-11-23.
"""
import os, sqlite3, sys

PREFIXES = ["OR", "CA", "ID", "NV"]
MIN_ROWS = {"OR": 11000, "CA": 21000, "ID": 32000, "NV": 220000}
MIN_TOTAL = 285000
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
        db.commit()
        db.execute("DETACH DATABASE src")
        print(f"{p}: {n} rows (minimum {MIN_ROWS[p]})")
        if n < MIN_ROWS[p]:
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
