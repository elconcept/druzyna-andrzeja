#!/usr/bin/env python3
"""Read-only, bounded SAOS candidate sampler.

Does not create gold labels, invent masked questions, or modify the live 22 GB
SQLite database. Default export is metadata+hashes, never full court text.
Full anonymized public text requires explicit --include-text.

Example on Synology:
  python3 scripts/saos_candidates.py \
    --db /volume2/docker/mcp-saos/data/saos.sqlite \
    --output /tmp/saos-candidates.jsonl --limit 100
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import zlib
from pathlib import Path
from urllib.parse import quote


def open_read_only(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(f"Brak bazy SQLite: {path}")
    uri = "file:" + quote(str(path.resolve()), safe="/") + "?mode=ro"
    db = sqlite3.connect(uri, uri=True, timeout=5)
    db.execute("PRAGMA query_only=ON")
    db.execute("PRAGMA busy_timeout=5000")
    return db


def case_numbers(raw: dict) -> list[str]:
    items = raw.get("courtCases") or []
    if not isinstance(items, list):
        return []
    result = []
    for item in items:
        if isinstance(item, dict):
            num = item.get("caseNumber")
        else:
            num = item if isinstance(item, str) else None
        if isinstance(num, str) and num.strip():
            result.append(num.strip())
    return sorted(set(result))


def candidate(row: tuple, min_chars: int, include_text: bool) -> dict | None:
    row_id, court_type, date, payload = row
    document = json.loads(zlib.decompress(payload).decode("utf-8"))
    if not isinstance(document, dict):
        return None
    body = document.get("textContent")
    if not isinstance(body, str) or len(body.strip()) < min_chars:
        return None
    bases = document.get("legalBases") or []
    if not isinstance(bases, list) or not bases:
        return None
    entry = {
        "dataset": "saos-local-candidates",
        "label_status": "unverified_no_gold",
        "source_id": row_id,
        "court_type": court_type,
        "judgment_date": date,
        "case_numbers": case_numbers(document),
        "text_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "text_chars": len(body),
        "legal_bases_count": len(bases),
        "has_referenced_regulations": bool(document.get("referencedRegulations")),
    }
    if include_text:
        entry["text_content"] = body
        entry["legal_bases_unverified"] = bases
    return entry


def sample(db: sqlite3.Connection, start_id: int, limit: int,
           min_chars: int, include_text: bool, scan_limit: int) -> tuple[list[dict], dict]:
    found = []
    scanned = 0
    skipped = 0
    errors = 0
    last = start_id
    while len(found) < limit and scanned < scan_limit:
        batch = min(250, scan_limit - scanned)
        rows = db.execute(
            "SELECT id, court_type, judgment_date, data FROM judgments "
            "WHERE id > ? ORDER BY id LIMIT ?", (last, batch)
        ).fetchall()
        if not rows:
            break
        for row in rows:
            last = row[0]
            scanned += 1
            try:
                x = candidate(row, min_chars, include_text)
            except (json.JSONDecodeError, UnicodeError, zlib.error, TypeError, ValueError):
                errors += 1
                continue
            if x is None:
                skipped += 1
                continue
            found.append(x)
            if len(found) == limit:
                break
    return found, {
        "selected": len(found), "scanned": scanned,
        "skipped": skipped, "decode_errors": errors, "last_id": last,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--scan-limit", type=int, default=10000)
    parser.add_argument("--start-id", type=int, default=0)
    parser.add_argument("--min-chars", type=int, default=500)
    parser.add_argument("--include-text", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.limit <= 1000:
        parser.error("--limit musi należeć do zakresu 1–1000")
    if not args.limit <= args.scan_limit <= 50000:
        parser.error("--scan-limit musi być >= --limit i <= 50000")
    if args.start_id < 0 or args.min_chars < 0:
        parser.error("Ujemne wartości są niedozwolone")
    if not args.output.parent.is_dir():
        parser.error("Folder docelowy nie istnieje")
    with open_read_only(args.db) as db:
        items, audit = sample(db, args.start_id, args.limit,
                              args.min_chars, args.include_text, args.scan_limit)
    if not items:
        print("Brak kandydatów spełniających warunki.", file=sys.stderr)
        return 2
    tmp = args.output.with_name(args.output.name + "." + str(os.getpid()) + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as fh:
            for item in items:
                fh.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
        os.replace(tmp, args.output)
    finally:
        tmp.unlink(missing_ok=True)
    print(json.dumps({**audit, "output": str(args.output),
                      "contains_text": args.include_text}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
