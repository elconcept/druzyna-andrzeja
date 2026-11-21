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


## Katalog propozycji — https://dan.xlap.pl

- **catalog/feeds.toml** — lista katalogów zewnętrznych w TOML. Aktualnie importuje Vaquill-AI/awesome-legaltech. Zmiana tej listy nie dodaje submodułów.
- **scripts/catalog.py** — import pozycji z README, łączenie powtórzonych URL i pobieranie metryk GitHub: gwiazdek, contributorów, otwartych PR, ostatnich commitów, forków i stanu archiwizacji.
- **catalog/proposals.json** — automatycznie generowany snapshot. Nie edytować ręcznie.
- **web/** — interfejs do wyszukiwania, tagowania, filtrowania i sortowania propozycji.
- **.github/workflows/catalog.yml** — automatyczne odświeżanie co sześć godzin, testy, zapis snapshotu, artefakt strony oraz HTTP smoke test https://dan.xlap.pl.

**Zatwierdzanie:** wybierz przy repozytorium GitHub „Kopiuj wpis TOML”, wklej do [sources.toml](https://github.com/elconcept/druzyna-andrzeja/edit/main/sources.toml) i zatwierdź commit. Dopiero istniejący workflow sync.yml doda je do katalogów _vendor i _workbench. Strona publiczna nie może modyfikować sources.toml i nie ma dostępu do tokenu GitHub. Linki spoza GitHub pozostają propozycjami informacyjnymi, nie są automatycznie submodułami.

**Publikacja:** Cloudflare Worker `druzyna-andrzeja` (źródło: [deploy/worker.js](deploy/worker.js)) obsługuje trasę `dan.xlap.pl/*` i pobiera zasoby z gałęzi `main` GitHub. DNS Cloudflare: `dan.xlap.pl` CNAME `elconcept.github.io`, proxy włączone; aktywną treść dostarcza Worker, nie GitHub Pages. Po aktualizacji `catalog/proposals.json` w Actions strona odczytuje nowy katalog (cache ok. 5 minut). Interfejs, CSS i JS również są czytane z GitHub. Workflow sprawdza faktyczny publiczny HTTP 200 i poprawność danych. Zmiana kodu samego Workera wymaga jego ponownego wdrożenia w Cloudflare.

**Test parsera:** python3 -m unittest discover -s tests -p 'test_catalog.py' -v.
