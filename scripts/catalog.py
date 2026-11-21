#!/usr/bin/env python3
"""Build a flat, read-only proposal catalog from human-edited TOML feeds.

Does not clone repositories, edit sources.toml, or touch _vendor/_workbench.
Python 3.11+ standard library only. GitHub metrics require GITHUB_TOKEN.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FEEDS = ROOT / "catalog" / "feeds.toml"
OUTPUT = ROOT / "catalog" / "proposals.json"
GH_REPO = re.compile(r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$", re.I)
ENTRY = re.compile(r"^\s*-\s+(?:\*\*)?\[([^\]]+)\]\((https?://[^\s)]+)\)")
HEADING = re.compile(r"^(#{2,3})\s+(.+?)\s*$")
INLINE_TAG = re.compile(r"\*\*\[([^\]]{1,60})\]\*\*")


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_url(url: str) -> str:
    parts = urllib.parse.urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    if parts.scheme not in ("https", "http") or not host:
        raise ValueError("Unsupported URL: " + url)
    # Retain path and non-tracking query for non-GitHub resources.
    path = parts.path.rstrip("/")
    if host == "www.github.com":
        host = "github.com"
    if host == "github.com":
        bits = path.strip("/").split("/")
        if len(bits) == 2:
            return "https://github.com/" + bits[0].lower() + "/" + bits[1].removesuffix(".git").lower()
    return urllib.parse.urlunsplit((parts.scheme, host, path, parts.query, ""))


def github_repo(url: str) -> tuple[str, str] | None:
    m = GH_REPO.fullmatch(url)
    return (m.group(1), m.group(2)) if m else None


def clean_description(s: str) -> str:
    s = re.sub(r"\*\*|\*(?=\s)|<[^>]+>", "", s)
    return re.sub(r"\s+", " ", s).strip(" -—\t")[:850]


def parse_readme(md: str, feed_name: str) -> list[dict]:
    section = ""
    subsection = ""
    entries: list[dict] = []
    for number, line in enumerate(md.splitlines(), 1):
        h = HEADING.match(line)
        if h:
            level, title = h.groups()
            if title.lower() == "contents":
                section, subsection = "Contents", ""
            elif level == "##":
                section, subsection = title, ""
            else:
                subsection = title
            continue
        m = ENTRY.match(line)
        if not m:
            continue
        title, url = m.groups()
        # Table of contents is navigation, not a catalog entry.
        if section == "Contents":
            continue
        try:
            url = normalize_url(url)
        except ValueError:
            continue
        tags = [x for x in (section, subsection) if x]
        tags.append("Prawo polskie")
        if feed_name.endswith("komercyjne"):
            tags.append("Komercyjne")
        if feed_name.endswith("archiwum"):
            tags.append("Archiwalne")
        rest = line[m.end():]
        for tag in INLINE_TAG.findall(rest):
            if tag not in tags:
                tags.append(tag)
        if "Archived" in section or re.search(r"\[Archived\b", line, re.I):
            tags.append("Archived")
        # International-only format not implemented in Polish law.
        if url == "https://docs.oasis-open.org/legaldocml/akn-core/v1.0/akn-core-v1.0-part1-vocabulary.html":
            continue
        entries.append({
            "id": hashlib.sha256(url.encode("utf-8")).hexdigest()[:16],
            "name": title.strip(),
            "url": url,
            "description": clean_description(rest),
            "tags": tags,
            "github": github_repo(url) is not None,
            "source": feed_name,
            "source_line": number,
        })
    return entries


def read_feeds() -> list[dict]:
    data = tomllib.loads(FEEDS.read_text(encoding="utf-8"))
    if data.get("version") != 1 or data.get("jurisdiction") != "PL" or not isinstance(data.get("feed"), list):
        raise ValueError("Expected version = 1, jurisdiction = 'PL', and [[feed]]")
    result = []
    for f in data["feed"]:
        if not isinstance(f, dict) or not all(isinstance(f.get(k), str) for k in ("name", "url")):
            raise ValueError("Each feed requires string name and url")
        if not f["url"].startswith("https://raw.githubusercontent.com/apiotrowski-afk/awesome-legaltech-pl/main/"):
            raise ValueError("Catalog must use approved Polish-law source only (awesome-legaltech-pl)")
        result.append(f)
    return result


def fetch(url: str, token: str = "", accept: str = "application/json") -> tuple[bytes, dict]:
    headers = {"User-Agent": "druzyna-andrzeja-catalog/1", "Accept": accept}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=35) as r:
        return r.read(), dict(r.headers)


def graphql(batch: list[tuple[str, str]], token: str) -> dict[str, dict]:
    if not token:
        return {}
    blocks = []
    for i, (owner, name) in enumerate(batch):
        blocks.append(
            f'r{i}: repository(owner:{json.dumps(owner)}, name:{json.dumps(name)}) '
            '{ stargazerCount forkCount isArchived isPrivate pushedAt '
            'pullRequests(states:OPEN){totalCount} '
            'defaultBranchRef{target{... on Commit{committedDate oid}}} '
            'primaryLanguage{name} repositoryTopics(first:12){nodes{topic{name}}} }'
        )
    payload = json.dumps({"query": "query {\n" + "\n".join(blocks) + "\n}"}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.github.com/graphql", data=payload, method="POST",
        headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json", "User-Agent": "druzyna-andrzeja-catalog/1"},
    )
    with urllib.request.urlopen(req, timeout=40) as response:
        body = json.load(response)
    if body.get("errors") and not body.get("data"):
        raise RuntimeError("GitHub GraphQL returned errors")
    results = {}
    for i, repo in enumerate(batch):
        node = (body.get("data") or {}).get("r" + str(i))
        if not node:
            continue
        commit = (((node.get("defaultBranchRef") or {}).get("target")) or {})
        results[repo[0].lower() + "/" + repo[1].lower()] = {
            "stars": node.get("stargazerCount"),
            "forks": node.get("forkCount"),
            "open_prs": (node.get("pullRequests") or {}).get("totalCount"),
            "last_commit": commit.get("committedDate"),
            "last_commit_sha": commit.get("oid"),
            "archived": node.get("isArchived"),
            "language": (node.get("primaryLanguage") or {}).get("name"),
            "github_topics": [n["topic"]["name"] for n in
                              (node.get("repositoryTopics") or {}).get("nodes", [])
                              if n and n.get("topic")],
        }
    return results


def contributors(owner: str, repo: str, token: str) -> int | None:
    # Fetch 1 contributor and read the last-page number from Link; no full pagination.
    url = "https://api.github.com/repos/" + urllib.parse.quote(owner) + "/" + urllib.parse.quote(repo) + "/contributors?per_page=1&anon=true"
    data, headers = fetch(url, token=token)
    if not data:
        return 0
    rows = json.loads(data)
    if not isinstance(rows, list):
        return None
    link = headers.get("Link", "")
    m = re.search(r'[?&]page=(\d+)>;\s*rel="last"', link)
    return int(m.group(1)) if m else len(rows)


def active_urls() -> set[str]:
    data = tomllib.loads((ROOT / "sources.toml").read_text(encoding="utf-8"))
    return {normalize_url(item["url"]) for item in data.get("repo", [])
            if isinstance(item, dict) and isinstance(item.get("url"), str)}


def build(no_metadata: bool = False, markdown_file: str | None = None) -> dict:
    feeds = read_feeds()
    by_url: dict[str, dict] = {}
    for feed in feeds:
        if markdown_file:
            md = Path(markdown_file).read_text(encoding="utf-8")
        else:
            md = fetch(feed["url"], accept="text/plain")[0].decode("utf-8")
        for item in parse_readme(md, feed["name"]):
            old = by_url.get(item["url"])
            if old is None:
                by_url[item["url"]] = item
            else:
                old["tags"] = sorted(set(old["tags"]) | set(item["tags"]))
                # Keep first display name; preserve multiple source positions.
    entries = sorted(by_url.values(), key=lambda p: (p["name"].casefold(), p["url"]))
    active = active_urls()
    cached: dict[str, dict] = {}
    if OUTPUT.is_file():
        try:
            old_data = json.loads(OUTPUT.read_text(encoding="utf-8"))
            cached = {v["url"]: v.get("metrics", {}) for v in old_data.get("proposals", [])}
        except (OSError, ValueError, KeyError):
            pass
    for item in entries:
        item["approved"] = item["url"] in active
        if item["github"]:
            item["metrics"] = cached.get(item["url"], {})
        else:
            item["metrics"] = {}

    token = os.environ.get("GITHUB_TOKEN", "")
    if token and not no_metadata:
        lookup: dict[str, list[dict]] = {}
        for item in entries:
            pair = github_repo(item["url"])
            if pair:
                key = pair[0].lower() + "/" + pair[1].lower()
                lookup.setdefault(key, []).append(item)
        keys = sorted(lookup)
        # A single batched request reads stars, PR counts, branch commit and tags.
        for start in range(0, len(keys), 30):
            chunk = keys[start:start + 30]
            try:
                metrics = graphql([tuple(key.split("/", 1)) for key in chunk], token)
                for key, value in metrics.items():
                    for item in lookup[key]:
                        item["metrics"] = {**item["metrics"], **value}
            except (urllib.error.URLError, ValueError, RuntimeError) as exc:
                print("Metadata GraphQL unavailable for batch: " + str(exc), file=sys.stderr)
        # REST Link header supplies the contributor total without fetching every page.
        for key in keys:
            owner, repo = key.split("/", 1)
            try:
                count = contributors(owner, repo, token)
                for item in lookup[key]:
                    item["metrics"]["contributors"] = count
            except (urllib.error.URLError, ValueError) as exc:
                print("Contributors unavailable for " + key + ": " + str(exc), file=sys.stderr)
            time.sleep(0.10)

    result = {
        "schema": 1, "jurisdiction": "PL", "generated_at": now(),
        "feeds": [{"name": f["name"], "url": f["url"]} for f in feeds],
        "count": len(entries),
        "github_count": sum(1 for p in entries if p["github"]),
        "approved_count": sum(1 for p in entries if p["approved"]),
        "proposals": entries,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    OUTPUT.write_text(encoded, encoding="utf-8")
    print(f"Catalog: {result['count']} proposals ({result['github_count']} GitHub); "
          f"{result['approved_count']} approved; {OUTPUT}")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-metadata", action="store_true")
    parser.add_argument("--markdown-file", help="Offline test fixture")
    args = parser.parse_args()
    try:
        build(no_metadata=args.no_metadata, markdown_file=args.markdown_file)
    except Exception as exc:
        print("Catalog update failed: " + str(exc), file=sys.stderr)
        raise SystemExit(1)
