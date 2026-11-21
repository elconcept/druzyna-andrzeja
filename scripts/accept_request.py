#!/usr/bin/env python3
"""Accept a public, GitHub-authenticated fetch request for a listed PL repo.

Only catalog entries with public, licensed GitHub sources qualify. No arbitrary
URLs, branches, shell execution, or third-party code is accepted from an issue.
The script edits only sources.toml. sync.yml performs the actual download.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path

FETCH_TITLE = re.compile(r"^fetch: ([A-Za-z0-9_.-]{1,100})/([A-Za-z0-9_.-]{1,100})$", re.I)
MAX_REPOS = 32
MAX_SIZE_KIB = 25000


def decide(issue: dict, metadata: dict, catalog: dict, current: str) -> tuple[str, str, str]:
    title = (issue.get("title") or "").strip()
    match = FETCH_TITLE.fullmatch(title)
    if not match:
        return "ignored", "To nie jest zgłoszenie pobrania repozytorium.", current
    slug = (match.group(1) + "/" + match.group(2)).lower()
    url = "https://github.com/" + slug
    if catalog.get("jurisdiction") != "PL" or not any(
        p.get("github") and p.get("url", "").lower() == url
        for p in catalog.get("proposals", [])
    ):
        return "rejected", "Repozytorium nie znajduje się w zatwierdzonej liście propozycji dotyczących prawa polskiego.", current
    full_name = (metadata.get("full_name") or "").lower()
    if full_name != slug or metadata.get("private") or metadata.get("archived"):
        return "rejected", "Repozytorium musi być publiczne, niezarchiwizowane i zgodne z podanym adresem.", current
    size = metadata.get("size")
    if not isinstance(size, int) or size > MAX_SIZE_KIB:
        return "rejected", f"Repozytorium przekracza limit {MAX_SIZE_KIB} KiB na publiczną kopię analityczną.", current
    license_info = metadata.get("license") or {}
    license_spdx = license_info.get("spdx_id") if isinstance(license_info, dict) else None
    if not license_spdx or license_spdx == "NOASSERTION":
        return "rejected", "Brak rozpoznanej licencji pozwalającej na publiczne rozpowszechnianie kopii _workbench. Zachowano link do źródła, bez kopiowania.", current
    try:
        parsed = tomllib.loads(current)
    except tomllib.TOMLDecodeError:
        return "error", "sources.toml zawiera niepoprawny TOML.", current
    if parsed.get("version") != 1:
        return "error", "Niewłaściwa wersja sources.toml.", current
    existing = parsed.get("repo") or []
    if not isinstance(existing, list):
        return "error", "Nieprawidłowa lista [[repo]] w sources.toml.", current
    normalized = {str(x.get("url", "")).lower().removesuffix(".git") for x in existing}
    if url in normalized:
        return "already", "Repozytorium już jest na liście źródeł; synchronizacja działa automatycznie.", current
    if len(existing) >= MAX_REPOS:
        return "rejected", f"Przekroczono limit {MAX_REPOS} aktywnych repozytoriów; katalog jest chroniony przed niekontrolowanym wzrostem.", current
    repo_name = re.sub(r"[^a-z0-9_-]+", "-", slug.replace("/", "-")).strip("-")[:100]
    if not repo_name or not repo_name[0].isalpha():
        repo_name = "repo-" + repo_name
    if any(x.get("name") == repo_name for x in existing):
        return "rejected", "Kolizja nazwy katalogu; nie dopisuję automatycznie źródła.", current
    record = f'\n[[repo]]\nname = "{repo_name}"\nurl = "{url}.git"\n'
    return "added", f"Przyjęto {slug} (licencja {license_spdx}); uruchamiana synchronizacja upstream.", current.rstrip("\n") + "\n" + record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issue-json", type=Path, required=True)
    parser.add_argument("--repo-json", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, default=Path("catalog/proposals.json"))
    parser.add_argument("--sources", type=Path, default=Path("sources.toml"))
    parser.add_argument("--outcome", type=Path, required=True)
    args = parser.parse_args()
    issue = json.loads(args.issue_json.read_text(encoding="utf-8"))
    metadata = json.loads(args.repo_json.read_text(encoding="utf-8"))
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    current = args.sources.read_text(encoding="utf-8")
    status, message, updated = decide(issue, metadata, catalog, current)
    if status == "added":
        args.sources.write_text(updated, encoding="utf-8")
    args.outcome.write_text(json.dumps({"status": status, "message": message}, ensure_ascii=False), encoding="utf-8")
    print(status + ": " + message)
    return 1 if status == "error" else 0


if __name__ == "__main__":
    sys.exit(main())
