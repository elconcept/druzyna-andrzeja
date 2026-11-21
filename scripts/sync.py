#!/usr/bin/env python3
"""Sync public upstream Git submodules and three-way-safe, noise-free analysis copies.

sources.toml is authoritative; _vendor is pinned upstream; _workbench retains edits.
No third-party Python dependencies (Python >= 3.11).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "_vendor"
WORKBENCH = ROOT / "_workbench"
LICENSES = ROOT / "_licenses"
STATE = ROOT / "_sync" / "state"
REPORT = ROOT / "_sync" / "last-run.md"
NAME_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
GITHUB_RE = re.compile(r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?$")
# Git control and license files: excluded from the *analysis* view only.
GIT_NOISE = frozenset({".git", ".gitignore", ".dockerignore", ".gitmodules", ".gitattributes", ".gitkeep"})
LICENSE_RE = re.compile(r"^(license|licence|copying)(?:$|[._ -].*)", re.IGNORECASE)


class SyncError(RuntimeError):
    pass


def git(*args: str, cwd: Path = ROOT, capture: bool = True) -> str:
    proc = subprocess.run(["git", *args], cwd=cwd, text=True,
                          stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.PIPE if capture else None,
                          check=False)
    if proc.returncode:
        msg = (proc.stderr or "").strip() if capture else ""
        raise SyncError(f"git {' '.join(args)}: {msg or f'kod {proc.returncode}'}")
    return proc.stdout.strip() if capture else ""


@dataclass(frozen=True)
class Repo:
    name: str
    url: str
    branch: str | None


def parse_sources() -> list[Repo]:
    try:
        raw = tomllib.loads((ROOT / "sources.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise SyncError(f"Nie można odczytać sources.toml: {exc}") from exc
    if raw.get("version") != 1:
        raise SyncError("sources.toml: wymagane version = 1")
    entries = raw.get("repo", [])
    if not isinstance(entries, list):
        raise SyncError("sources.toml: użyj bloków [[repo]]")
    if set(raw) - {"version", "repo"}:
        raise SyncError("Nieznane pola główne sources.toml")
    seen: set[str] = set()
    result: list[Repo] = []
    for i, d in enumerate(entries, 1):
        if not isinstance(d, dict) or set(d) - {"name", "url", "branch"}:
            raise SyncError(f"[[repo]] nr {i}: nieznane pola")
        name, url, branch = d.get("name"), d.get("url"), d.get("branch")
        if not isinstance(name, str) or not NAME_RE.fullmatch(name):
            raise SyncError(f"[[repo]] nr {i}: name musi być krótką nazwą a-z, 0-9, _ lub -")
        if name in seen:
            raise SyncError(f"Duplikat nazwy źródła: {name}")
        seen.add(name)
        local_allowed = os.environ.get("DRUZYNA_ALLOW_LOCAL_TEST_URLS") == "1"
        if not isinstance(url, str) or not (GITHUB_RE.fullmatch(url) or (local_allowed and url.startswith("file://"))):
            raise SyncError(f"{name}: URL musi wskazywać publiczne repo https://github.com/OWNER/REPO.git")
        if branch is not None:
            if not isinstance(branch, str) or not branch or not re.fullmatch(r"[A-Za-z0-9._/-]+", branch):
                raise SyncError(f"{name}: nieprawidłowe branch")
            git("check-ref-format", "--branch", branch)
        result.append(Repo(name, url, branch))
    return sorted(result, key=lambda r: r.name)


def submodule_entries() -> dict[str, str]:
    out = git("ls-files", "--stage", "-z", "--", "_vendor")
    # `git` emits NUL; Python str.strip() only touches whitespace, not NUL.
    entries: dict[str, str] = {}
    for item in out.split("\0"):
        if not item:
            continue
        left, sep, path = item.partition("\t")
        if sep and left.split(" ")[0] == "160000":
            entries[path] = left.split(" ")[1]
    return entries


def modules_config(repos: list[Repo]) -> str:
    blocks = []
    for r in repos:
        lines = [f'[submodule "{r.name}"]', f'\tpath = _vendor/{r.name}', f'\turl = {r.url}']
        if r.branch:
            lines.append(f'\tbranch = {r.branch}')
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def atomic_write_if_changed(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() == content:
        return
    temp = path.with_name(path.name + ".tmp")
    try:
        temp.write_bytes(content)
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def discover_default_branch(url: str) -> str:
    out = git("ls-remote", "--symref", url, "HEAD")
    for line in out.splitlines():
        if line.startswith("ref: refs/heads/") and line.endswith("\tHEAD"):
            branch = line.removeprefix("ref: refs/heads/").removesuffix("\tHEAD")
            git("check-ref-format", "--branch", branch)
            return branch
    raise SyncError(f"Nie udało się rozpoznać gałęzi domyślnej: {url}")


def check_clean_upstream(path: Path) -> None:
    # If someone edited upstream checkout, abort: never reset their data.
    if git("status", "--porcelain", "--untracked-files=all", cwd=path):
        raise SyncError(f"{path.relative_to(ROOT)}: submoduł ma lokalne zmiany; nie nadpisuję")


def sync_submodules(repos: list[Repo], refresh: bool) -> dict[str, str]:
    VENDOR.mkdir(exist_ok=True)
    desired = {f"_vendor/{r.name}" for r in repos}
    before = submodule_entries()
    # Removal of a configured source detaches the upstream submodule only.
    # Workbench and its state are intentionally retained.
    for name in sorted(set(before) - desired):
        if not name.startswith("_vendor/") or not NAME_RE.fullmatch(name.split("/", 1)[1]):
            raise SyncError(f"Niebezpieczna ścieżka usuwanego submodułu: {name}")
        folder = ROOT / name
        if folder.is_dir() and (folder / ".git").exists():
            check_clean_upstream(folder)
        git("rm", "-f", "--", name)
    for r in repos:
        rel = f"_vendor/{r.name}"
        target = ROOT / rel
        if rel not in before:
            cmd = ["submodule", "add", "--name", r.name]
            if r.branch:
                cmd += ["--branch", r.branch]
            cmd += [r.url, rel]
            git(*cmd)
        else:
            # The current checkout's .gitmodules may be out of sync with TOML.
            # A fresh checkout can contain only the gitlink without a directory.
            if not target.is_dir() or not (target / ".git").exists():
                # The authoritative .gitmodules is written before this command.
                git("submodule", "update", "--init", "--", rel)
    atomic_write_if_changed(ROOT / ".gitmodules", modules_config(repos).encode("utf-8"))
    if repos:
        git("submodule", "sync")
    revisions: dict[str, str] = {}
    for r in repos:
        target = VENDOR / r.name
        # New sources were cloned above; existing sources are at pinned SHA.
        check_clean_upstream(target)
        if refresh:
            branch = r.branch or discover_default_branch(r.url)
            git("fetch", "--quiet", "--no-tags", "origin", f"refs/heads/{branch}", cwd=target)
            new_commit = git("rev-parse", "FETCH_HEAD", cwd=target)
            git("checkout", "--quiet", "--detach", new_commit, cwd=target)
            # This explicit fetch records the pinned commit in the superproject.
            git("add", "--", f"_vendor/{r.name}")
        # Check out any nested pinned submodules, do not pull their HEAD independently.
        git("submodule", "update", "--init", "--recursive", "--quiet", cwd=target)
        check_clean_upstream(target)
        revisions[r.name] = git("rev-parse", "HEAD", cwd=target)
    return revisions


def is_license(name: str) -> bool:
    return bool(LICENSE_RE.fullmatch(name))


def category(rel: Path) -> str:
    if any(part.lower() in GIT_NOISE for part in rel.parts):
        return "skip"
    if is_license(rel.name):
        return "license"
    return "workbench"


def safe_symlink(root: Path, path: Path) -> None:
    link = os.readlink(path)
    if os.path.isabs(link) or not (path.parent / link).resolve(strict=False).is_relative_to(root.resolve()):
        raise SyncError(f"Symlink wychodzi poza źródło: {path.relative_to(root)} -> {link}")


def fingerprint(path: Path) -> dict[str, Any] | None:
    if not os.path.lexists(path):
        return None
    if path.is_symlink():
        return {"kind": "symlink", "target": os.readlink(path)}
    if path.is_file():
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return {"kind": "file", "sha256": h.hexdigest(),
                "executable": bool(path.stat().st_mode & 0o111)}
    if path.is_dir():
        return {"kind": "directory"}
    raise SyncError(f"Nieobsługiwany typ pliku: {path}")


def inventory(root: Path) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    work: dict[str, dict[str, Any]] = {}
    licenses: dict[str, dict[str, Any]] = {}

    def walk(d: Path) -> None:
        for child in sorted(d.iterdir()):
            rel = child.relative_to(root)
            kind = category(rel)
            if kind == "skip":
                continue
            if child.is_symlink():
                safe_symlink(root, child)
            elif child.is_dir():
                walk(child)
                continue
            fp = fingerprint(child)
            assert fp is not None
            (licenses if kind == "license" else work)[rel.as_posix()] = fp

    walk(root)
    return work, licenses


@dataclass
class Result:
    added: int = 0
    updated: int = 0
    deleted: int = 0
    unchanged: int = 0
    preserved: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)


def copy_entry(src: Path, dst: Path) -> None:
    """Atomically replace a file/symlink; never unlink the prior version first."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    temp = dst.with_name(f".{dst.name}.druzyna-sync-{os.getpid()}")
    if os.path.lexists(temp):
        raise SyncError(f"Plik tymczasowy już istnieje: {temp}")
    try:
        if src.is_symlink():
            os.symlink(os.readlink(src), temp)
        else:
            shutil.copy2(src, temp)
        temp.replace(dst)
    finally:
        if os.path.lexists(temp):
            temp.unlink()


def trim_empty_dirs(folder: Path, root: Path) -> None:
    while folder != root and folder.is_relative_to(root):
        try:
            folder.rmdir()
        except OSError:
            break
        folder = folder.parent


def apply_3way(source: Path, mirror: Path, previous: dict[str, Any],
               current: dict[str, Any]) -> Result:
    mirror.mkdir(parents=True, exist_ok=True)
    result = Result()
    # Local changes are recognized by comparison with *previous* upstream,
    # not by comparison with the newly pulled files.
    for rel in sorted(set(previous) | set(current)):
        dst, src = mirror / rel, source / rel
        old, new = previous.get(rel), current.get(rel)
        local = fingerprint(dst)
        if old == new:
            result.unchanged += 1
            continue
        if new is None:
            if local is None:
                result.unchanged += 1
            elif local == old:
                dst.unlink()
                trim_empty_dirs(dst.parent, mirror)
                result.deleted += 1
            else:
                result.preserved.append(f"{rel} — upstream usunął plik, lokalna wersja zachowana")
            continue
        if local == new:
            result.unchanged += 1
            continue
        if local is None and old is not None:
            result.preserved.append(f"{rel} — lokalne usunięcie zachowane")
            continue
        if local is not None and local != old:
            reason = "kolizja z plikiem lokalnym" if old is None else "lokalna modyfikacja"
            result.preserved.append(f"{rel} — {reason}; upstream nie nadpisany")
            continue
        # New source (no destination), or destination unmodified since old upstream.
        try:
            copy_entry(src, dst)
        except (OSError, ValueError, SyncError) as exc:
            result.conflicts.append(f"{rel}: {exc}")
        else:
            if local is None:
                result.added += 1
            else:
                result.updated += 1
    return result


def load_state(name: str, url: str) -> tuple[dict[str, Any], dict[str, Any]]:
    path = STATE / f"{name}.json"
    if not path.exists():
        return {}, {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise SyncError(f"Uszkodzony stan {path}: {exc}") from exc
    if obj.get("version") != 1 or obj.get("url") != url:
        raise SyncError(f"{name}: zmieniono źródło lub wersję stanu; nie nadpisuję istniejącego workbench")
    return obj.get("workbench", {}), obj.get("licenses", {})


def sync_one(repo: Repo, sha: str) -> tuple[Result, Result]:
    work, licenses = inventory(VENDOR / repo.name)
    prev_work, prev_licenses = load_state(repo.name, repo.url)
    result_work = apply_3way(VENDOR / repo.name, WORKBENCH / repo.name, prev_work, work)
    result_licenses = apply_3way(VENDOR / repo.name, LICENSES / repo.name, prev_licenses, licenses)
    if result_work.conflicts or result_licenses.conflicts:
        # Partial file-system errors must not advance baseline: a later run can retry.
        raise SyncError(f"{repo.name}: błędy plikowe: {result_work.conflicts + result_licenses.conflicts}")
    state = {"version": 1, "url": repo.url, "revision": sha,
             "workbench": work, "licenses": licenses}
    atomic_write_if_changed(STATE / f"{repo.name}.json",
                            (json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    return result_work, result_licenses


def report_divergence(name: str) -> tuple[list[str], list[str], list[str]]:
    """Stable view of workbench changes; identical on repeated no-op runs."""
    state = json.loads((STATE / f"{name}.json").read_text(encoding="utf-8"))
    expected = state["workbench"]
    root = WORKBENCH / name
    changed: list[str] = []
    removed: list[str] = []
    extra: list[str] = []
    for rel, wanted in sorted(expected.items()):
        got = fingerprint(root / rel)
        if got is None:
            removed.append(rel)
        elif got != wanted:
            changed.append(rel)

    def walk(base: Path) -> None:
        for child in sorted(base.iterdir()):
            rel = child.relative_to(root)
            kind = category(rel)
            if kind == "skip":
                continue
            if child.is_dir() and not child.is_symlink():
                walk(child)
            elif kind == "workbench" and rel.as_posix() not in expected:
                extra.append(rel.as_posix())

    if root.exists():
        walk(root)
    return changed, removed, extra


def write_report(repos: list[Repo], results: dict[str, tuple[str, Result, Result]]) -> None:
    lines = ["# Stan synchronizacji upstream", "", "Źródło: `sources.toml`; wersja źródłowa: `_vendor/`.", ""]
    if not repos:
        lines += ["Brak aktywnych źródeł. Dodaj bloki `[[repo]]` do `sources.toml`.", ""]
    else:
        lines += ["| Repo | Upstream SHA | Zmiany lokalne | Lokalne usunięcia | Dodatki / pozostałości |",
                  "|---|---|---:|---:|---:|"]
        divergences: dict[str, tuple[list[str], list[str], list[str]]] = {}
        for repo in repos:
            sha, _, _ = results[repo.name]
            changed, removed, extra = report_divergence(repo.name)
            divergences[repo.name] = changed, removed, extra
            lines.append(f"| `{repo.name}` | `{sha[:12]}` | {len(changed)} | {len(removed)} | {len(extra)} |")
        lines += ["", "## Pliki chronione przed nadpisaniem", ""]
        any_divergence = False
        for repo in repos:
            changed, removed, extra = divergences[repo.name]
            for kind, paths in (("lokalna modyfikacja", changed),
                                ("lokalne usunięcie", removed),
                                ("dodatkowy plik lub pozostałość po usunięciu upstream", extra)):
                for path in paths:
                    any_divergence = True
                    lines.append(f"- `{repo.name}/{path}` — {kind}")
        if not any_divergence:
            lines.append("Brak zmian względem aktualnego upstream.")
        lines.append("")
    active = {r.name for r in repos}
    orphans = sorted(p.name for p in WORKBENCH.iterdir() if p.is_dir() and p.name not in active) if WORKBENCH.is_dir() else []
    if orphans:
        lines += ["## Zachowane po usunięciu źródła", "", *(f"- `_workbench/{name}/` (nie jest już synchronizowany)" for name in orphans), ""]
    atomic_write_if_changed(REPORT, ("\n".join(lines).rstrip() + "\n").encode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="pobierz najnowsze commity upstream")
    args = parser.parse_args()
    if sys.version_info < (3, 11):
        raise SyncError("Wymagany Python >= 3.11")
    git("rev-parse", "--show-toplevel")
    repos = parse_sources()
    revisions = sync_submodules(repos, args.refresh)
    results: dict[str, tuple[str, Result, Result]] = {}
    for repo in repos:
        a, b = sync_one(repo, revisions[repo.name])
        results[repo.name] = revisions[repo.name], a, b
        print(f"{repo.name} {revisions[repo.name][:12]}: +{a.added} ~{a.updated} -{a.deleted}, zachowano {len(a.preserved)}")
    write_report(repos, results)
    print("Raport: _sync/last-run.md")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SyncError as exc:
        print(f"BŁĄD: {exc}", file=sys.stderr)
        raise SystemExit(1)
