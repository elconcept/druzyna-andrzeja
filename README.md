# Drużyna Andrzeja

Publiczny agregator repozytoriów do analizy kodu.

- `sources.toml` — jedyna, edytowana ręcznie lista źródeł.
- `_vendor/<nazwa>/` — upstream **1:1**, przypięty jako submodule Git (nie edytować).
- `_workbench/<nazwa>/` — kopia do analizy: bez metadanych Git, `.gitignore`, `.dockerignore` i plików licencji; można dowolnie modyfikować.
- `_licenses/<nazwa>/` — oryginalne licencje usunięte z widoku roboczego (dla zgodności licencyjnej).
- `_sync/` — historia bazowa plików i raport konfliktów (automatycznie zarządzane).

## Dodawanie źródeł

Dopisz do `sources.toml`:

```toml
[[repo]]
name = "patron"
url = "https://github.com/matematicsolutions/patron.git"
branch = "main"  # opcjonalne
```

Commit na `main` uruchamia synchronizację. GitHub Actions sprawdza upstream co godzinę i robi commit tylko przy zmianie. Można uruchomić workflow ręcznie.

Lokalnie: `./bootstrap.sh` odtwarza wersje przypięte w submodułach, a `./bootstrap.sh --refresh` pobiera najnowsze wersje upstream. Wymagane: Git i Python 3.11+.

Zmiany w `_workbench/` są zachowywane: synchronizator zmienia tylko pliki identyczne z poprzednią wersją upstream. Zachowuje także lokalne usunięcia i nie nadpisuje kolizji. Konflikty są wypisywane w `_sync/last-run.md`. Aktualizacje nie dokonują automatycznych merge'y.

Usunięcie repozytorium z listy przestaje je synchronizować, usuwa submoduł `_vendor/` i **pozostawia `_workbench/`**, aby nie utracić pracy. Upstream może mieć dodatkowe wymagania licencyjne; przed publiczną redystrybucją trzeba je uwzględnić.
