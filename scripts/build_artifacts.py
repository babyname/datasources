#!/usr/bin/env python3
"""Build datasources artifacts from the single source of truth.

character.json (20-field consumer contract) is the SOLE source of truth.
SQLite and PostgreSQL artifacts are deterministic DERIVED products: given the
same JSON they produce byte-identical output (modulo SQLite metadata). This
prevents the three-form distribution from becoming three sources of truth —
the exact failure mode that a multi-form data supply invites.

Artifacts:
    dist/character.json       - canonical CSV/JSON form (the input)
    dist/character.sqlite3    - neutral 20-column SQLite table for fate/qiming loaders
    dist/character.pg.sql     - PostgreSQL DDL + COPY-ready INSERT statements
    dist/MANIFEST.json        - sha256 + row counts for every artifact

Consumers map the neutral 20-column table onto their own ent schema:
    fate (CE): 20 fields == its contract, direct load via dbinit
    qiming (EE): superset (23 fields); load 20, let ent defaults fill the rest

Usage:
    python3 scripts/build_artifacts.py --source /path/to/character.json
    python3 scripts/build_artifacts.py --self-test
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

# Keep in sync with verify_dataset.py FIELD_SPEC (single source of truth).
# order is fixed so generated DDL / INSERT columns are deterministic.
COLUMNS: list[tuple[str, str]] = [
    ("char", "TEXT NOT NULL"),
    ("unicode", "TEXT NOT NULL"),
    ("radical", "TEXT NOT NULL"),
    ("radical_stroke", "INTEGER NOT NULL"),
    ("simplified_stroke", "INTEGER NOT NULL"),
    ("traditional_stroke", "INTEGER NOT NULL"),
    ("kangxi_stroke", "INTEGER"),
    ("science_stroke", "INTEGER NOT NULL"),
    ("wu_xing", "TEXT NOT NULL"),
    ("source", "TEXT NOT NULL"),
    ("is_simplified", "INTEGER"),
    ("is_traditional", "INTEGER"),
    ("is_kangxi", "INTEGER"),
    ("is_variant", "INTEGER"),
    ("regular", "INTEGER"),
    ("nameable", "INTEGER"),
    ("pinyin", "TEXT"),
    ("meaning", "TEXT"),
    ("simplified_of_char", "TEXT"),
    ("variant_of_char", "TEXT"),
]
BOOL_COLUMNS = {
    "is_simplified", "is_traditional", "is_kangxi", "is_variant",
    "regular", "nameable",
}
# qiming ent character has 23 fields; the 20-field canonical JSON contains 4
# columns qiming cannot consume as scalars:
#   radical_stroke, science_stroke   -> not in qiming schema
#   simplified_of_char, variant_of_char -> qiming models these as EDGE relations,
#                                         not scalar columns
# "import on demand" means the PG artifact carries only qiming's 16 scalars.
PG_COLUMNS = [n for n, _ in COLUMNS if n not in {
    "radical_stroke", "science_stroke", "simplified_of_char", "variant_of_char",
}]
PG_TYPES = {
    "TEXT NOT NULL": "TEXT NOT NULL",
    "TEXT": "TEXT",
    "INTEGER NOT NULL": "INTEGER NOT NULL",
    "INTEGER": "INTEGER",
}


def _sql_literal(value: Any, column: str, dialect: str = "sqlite") -> str:
    """Serialize a value for INSERT. ent storage differs per dialect:
    SQLite: bool -> 0/1, Strings(JSON) -> JSON text
    PG:     bool -> TRUE/FALSE, Strings(JSON) -> JSONB (JSON text literal)
    ent v0.11.9: field.Strings == field.JSON(name, []string{}); PG TypeJSON ->
    JSONB, runtime json.Unmarshal. No SchemaType override in qiming schema, so
    a TEXT[] column would break ent reads. Both dialects carry JSON text; only
    the declared column type differs (TEXT vs JSONB).
    """
    if value is None:
        return "NULL"
    if column in BOOL_COLUMNS:
        if dialect == "pg":
            return "TRUE" if value else "FALSE"
        return "1" if value else "0"
    if column == "pinyin":
        items = value if isinstance(value, list) else []
        return "'" + json.dumps(items, ensure_ascii=False,
                                separators=(",", ":")).replace("'", "''") + "'"
    if isinstance(value, bool):
        if dialect == "pg":
            return "TRUE" if value else "FALSE"
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def load_source(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise SystemExit(f"source root is {type(data).__name__}, expected list")
    return data


def build_sqlite(records: list[dict[str, Any]], out: Path) -> dict[str, Any]:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    con = sqlite3.connect(out)
    cols = ", ".join(f'"{n}" {t}' for n, t in COLUMNS)
    con.execute(f"CREATE TABLE character ({cols})")
    con.execute("CREATE UNIQUE INDEX idx_character_char ON character(char)")
    con.execute("CREATE INDEX idx_character_wu_xing ON character(wu_xing)")
    names = ", ".join(f'"{n}"' for n, _ in COLUMNS)
    placeholders = ", ".join("?" for _ in COLUMNS)
    rows = [
        tuple(_sqlite_value(r.get(n), n) for n, _ in COLUMNS)
        for r in records
    ]
    con.executemany(f"INSERT INTO character ({names}) VALUES ({placeholders})", rows)
    con.commit()
    con.close()
    return {"rows": len(rows), "sha256": sha256(out)}


def _sqlite_value(value: Any, column: str) -> Any:
    if value is None:
        return None
    if column in BOOL_COLUMNS:
        return 1 if value else 0
    if column == "pinyin":
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return value


def build_pg_sql(records: list[dict[str, Any]], out: Path) -> dict[str, Any]:
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "-- Derived artifact from character.json. DO NOT EDIT BY HAND.",
        "-- Regenerate with: python3 scripts/build_artifacts.py",
        "CREATE TABLE IF NOT EXISTS character (",
    ]
    col_spec = dict(COLUMNS)
    defs = []
    for name in PG_COLUMNS:
        if name == "pinyin":
            pg = "JSONB"  # ent field.Strings -> TypeJSON -> JSONB on PG
        elif name in BOOL_COLUMNS:
            pg = "BOOLEAN"
        else:
            pg = PG_TYPES[col_spec[name]]
        defs.append(f"    {name} {pg}")
    defs.append("    id BIGSERIAL PRIMARY KEY")
    lines.append(",\n".join(defs))
    lines.append(");")
    lines.append("CREATE UNIQUE INDEX IF NOT EXISTS idx_character_char ON character(char);")
    lines.append("CREATE INDEX IF NOT EXISTS idx_character_wu_xing ON character(wu_xing);")
    cols = ", ".join(PG_COLUMNS)
    for r in records:
        vals = ", ".join(_sql_literal(r.get(n), n, "pg") for n in PG_COLUMNS)
        # idempotent: compose restarts / re-seeds must not duplicate rows.
        lines.append(
            f"INSERT INTO character ({cols}) VALUES ({vals}) "
            "ON CONFLICT (char) DO NOTHING;"
        )
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"rows": len(records), "sha256": sha256(out)}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_artifacts(dist: Path, manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for name, meta in manifest["artifacts"].items():
        p = dist / name
        if not p.exists():
            errors.append(f"{name}: missing")
            continue
        if sha256(p) != meta["sha256"]:
            errors.append(f"{name}: sha256 drift")
        if name.endswith(".sqlite3"):
            con = sqlite3.connect(p)
            n = con.execute("SELECT count(*) FROM character").fetchone()[0]
            con.close()
            if n != meta["rows"]:
                errors.append(f"{name}: rows {n} != {meta['rows']}")
    return errors


def build(source: Path, dist: Path) -> int:
    if not source.exists():
        print(f"FAIL source not found: {source}")
        return 1
    records = load_source(source)
    dist.mkdir(parents=True, exist_ok=True)
    canonical = dist / "character.json"
    canonical.write_text(
        json.dumps(records, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    sqlite3_meta = build_sqlite(records, dist / "character.sqlite3")
    pg_meta = build_pg_sql(records, dist / "character.pg.sql")
    manifest = {
        "source": str(source),
        "row_count": len(records),
        "column_count": len(COLUMNS),
        "columns": [n for n, _ in COLUMNS],
        "pg_columns": PG_COLUMNS,
        "pg_excluded": [n for n, _ in COLUMNS if n not in PG_COLUMNS],
        "artifacts": {
            "character.json": {"rows": len(records), "sha256": sha256(canonical)},
            "character.sqlite3": sqlite3_meta,
            "character.pg.sql": pg_meta,
        },
    }
    (dist / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    errors = verify_artifacts(dist, manifest)
    print(f"source  : {source}")
    print(f"rows    : {len(records)}")
    print(f"sqlite  : {sqlite3_meta['sha256'][:12]}  rows={sqlite3_meta['rows']}")
    print(f"pg sql  : {pg_meta['sha256'][:12]}  rows={pg_meta['rows']}")
    if errors:
        print(f"FAIL    : {len(errors)} error(s)")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("PASS    : all artifacts match MANIFEST")
    return 0


def self_test() -> int:
    """Prove artifact determinism and drift detection."""
    import tempfile
    records = [
        {"char": "木", "unicode": "U+6728", "radical": "木", "radical_stroke": 0,
         "simplified_stroke": 4, "traditional_stroke": 4, "kangxi_stroke": 4,
         "science_stroke": 4, "wu_xing": "木", "source": "test",
         "nameable": True, "pinyin": ["mù"]},
        {"char": "水", "unicode": "U+6C34", "radical": "水", "radical_stroke": 0,
         "simplified_stroke": 4, "traditional_stroke": 4, "kangxi_stroke": 4,
         "science_stroke": 4, "wu_xing": "水", "source": "test",
         "nameable": True, "pinyin": ["shuǐ"]},
    ]
    failures = 0
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        src = root / "in.json"
        src.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
        d1, d2 = root / "d1", root / "d2"
        build(src, d1)
        build(src, d2)
        for name in ("character.sqlite3", "character.pg.sql", "character.json"):
            a, b = sha256(d1 / name), sha256(d2 / name)
            ok = a == b
            print(f"  {'PASS' if ok else 'FAIL'}  deterministic: {name}")
            if not ok:
                failures += 1
        m1 = json.loads((d1 / "MANIFEST.json").read_text(encoding="utf-8"))
        ok = not verify_artifacts(d1, m1)
        print(f"  {'PASS' if ok else 'FAIL'}  must-miss: clean artifacts")
        if not ok:
            failures += 1
        (d1 / "character.pg.sql").write_text("-- tampered\n", encoding="utf-8")
        drift = verify_artifacts(d1, m1)
        ok = any("sha256 drift" in e for e in drift)
        print(f"  {'PASS' if ok else 'FAIL'}  must-hit: artifact drift")
        if not ok:
            failures += 1
        pg = (d2 / "character.pg.sql").read_text(encoding="utf-8")
        ok = ("INSERT INTO character" in pg and "水" in pg
              and "'[\"mù\"]'" in pg and "nameable BOOLEAN" in pg
              and "pinyin JSONB" in pg and ", TRUE," in pg
              and "ARRAY[" not in pg
              and "radical_stroke " not in pg.split("CREATE UNIQUE INDEX")[0])
        print(f"  {'PASS' if ok else 'FAIL'}  pg sql: qiming 16 scalars + JSONB dialect")
        if not ok:
            failures += 1
        sq = sqlite3.connect(d2 / "character.sqlite3")
        row = sq.execute(
            "SELECT nameable, pinyin FROM character WHERE char = '木'"
        ).fetchone()
        sq.close()
        ok = row == (1, '["mù"]')
        print(f"  {'PASS' if ok else 'FAIL'}  sqlite dialect: 0/1 + JSON text")
        if not ok:
            failures += 1
    print(f"== self-test: {'PASS' if failures == 0 else str(failures) + ' failures'} ==")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path,
                    default=Path(__file__).resolve().parents[1] / "dist" / "character.json")
    ap.add_argument("--dist", type=Path,
                    default=Path(__file__).resolve().parents[1] / "dist")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    return build(args.source, args.dist)


if __name__ == "__main__":
    sys.exit(main())
