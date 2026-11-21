#!/usr/bin/env bash
# One-time GitHub Pages activation using the repository owner's gh CLI session.
# GitHub Actions GITHUB_TOKEN cannot create the Pages site in every repository.
set -euo pipefail

repo="elconcept/druzyna-andrzeja"
domain="dan.xlap.pl"

if ! command -v gh >/dev/null 2>&1; then
  printf 'Wymagany gh CLI: https://cli.github.com/\n' >&2
  exit 1
fi

gh auth status >/dev/null

if gh api "repos/$repo/pages" >/dev/null 2>&1; then
  printf 'GitHub Pages już istnieje.\n'
else
  printf 'Włączam Pages (build_type=workflow)...\n'
  gh api --method POST "repos/$repo/pages" -f build_type=workflow >/dev/null
fi

printf 'Ustawiam domenę %s...\n' "$domain"
gh api --method PUT "repos/$repo/pages" -f build_type=workflow -f cname="$domain" >/dev/null

printf 'GitHub Pages włączone. Rekord DNS CNAME: dan -> elconcept.github.io\n'
printf 'Uruchom ponownie workflow katalogu w Actions po ustawieniu DNS.\n'
