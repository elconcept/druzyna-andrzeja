# Drużyna Andrzeja

Publiczny agregator repozytoriów i narzędzi **wyłącznie dotyczących prawa polskiego** do selekcji i analizy kodu. Serwis: [dan.xlap.pl](https://dan.xlap.pl).

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

- **catalog/feeds.toml** — lista katalogów zewnętrznych w TOML. Aktualnie importuje **wyłącznie** [awesome-legaltech-pl](https://github.com/apiotrowski-afk/awesome-legaltech-pl): README, KOMERCYJNE i ARCHIWUM. `jurisdiction = "PL"` jest obowiązkowe, a importer odrzuca globalną listę. Opisy źródłowe na licencji CC BY 4.0, z podaniem autora i linku. Zmiana tej listy nie dodaje submodułów.
- **scripts/catalog.py** — import pozycji z README, łączenie powtórzonych URL i pobieranie metryk GitHub: gwiazdek, contributorów, otwartych PR, ostatnich commitów, forków i stanu archiwizacji.
- **catalog/proposals.json** — automatycznie generowany snapshot. Nie edytować ręcznie.
- **web/** — interfejs do wyszukiwania, tagowania, filtrowania i sortowania propozycji.
- **.github/workflows/catalog.yml** — automatyczne odświeżanie co sześć godzin, testy, zapis snapshotu, artefakt strony oraz HTTP smoke test https://dan.xlap.pl.

**Zatwierdzanie:** wybierz przy repozytorium GitHub „Kopiuj wpis TOML”, wklej do [sources.toml](https://github.com/elconcept/druzyna-andrzeja/edit/main/sources.toml) i zatwierdź commit. Dopiero istniejący workflow sync.yml doda je do katalogów _vendor i _workbench. Strona publiczna nie może modyfikować sources.toml i nie ma dostępu do tokenu GitHub. Linki spoza GitHub pozostają propozycjami informacyjnymi, nie są automatycznie submodułami.

**Publikacja:** Cloudflare Worker `druzyna-andrzeja` (źródło: [deploy/worker.js](deploy/worker.js)) obsługuje trasę `dan.xlap.pl/*` i pobiera zasoby z gałęzi `main` GitHub. DNS Cloudflare: `dan.xlap.pl` CNAME `elconcept.github.io`, proxy włączone; aktywną treść dostarcza Worker, nie GitHub Pages. Po aktualizacji `catalog/proposals.json` w Actions strona odczytuje nowy katalog (cache ok. 5 minut). Interfejs, CSS i JS również są czytane z GitHub. Workflow sprawdza faktyczny publiczny HTTP 200 i poprawność danych. Zmiana kodu samego Workera wymaga jego ponownego wdrożenia w Cloudflare.


### Ranking repozytoriów i przeglądanie kodu

Lista jest płaska, z filtrem kategorii i tagów oraz sortowaniem według wskaźnika 0–100, gwiazdek, forków, contributorów, daty ostatniego commita, otwartych PR i nazwy.

**Potencjał techniczny** (repo-health-v1): maks. 25 pkt za gwiazdki, 10 pkt za forki (skala logarytmiczna), 40 pkt za świeżość ostatniego commita (spadek wykładniczy z czasem 260 dni), 20 pkt za liczbę kont contributorów powiązanych z GitHub, 5 pkt za licencję SPDX. Kara −35 za archiwizację. Brak danych nie jest oceniany jako zero. Wskaźnik **nie ocenia prawidłowości prawa, bezpieczeństwa ani jakości kodu**. Otwarte PR i issues są pokazywane, ale nie punktowane — bez analizy kontekstu ich liczba nie świadczy jednoznacznie o utrzymaniu. Wzór: [scripts/catalog.py](scripts/catalog.py).

Przycisk **Przeglądaj pliki** otwiera wbudowane drzewo Git z podglądem tekstu do 250 KB. Endpointy Cloudflare Workera ([deploy/worker.js](deploy/worker.js)) ograniczają dostęp do repozytoriów z polskiego katalogu i odwołań do konkretnego commita, buforują odczyty z publicznego GitHub i nie przyjmują tokenów użytkownika. Dla dużych i binarnych plików oraz pełnej nawigacji użyj linku [GitHub.dev](https://github.dev) przy każdej karcie.

### Baza danych i zapis

GitHub Pages jest statycznym hostingiem, a nie bazą danych. Obecny katalog wykorzystuje JSON wersjonowany w Git i aktualizowany przez GitHub Actions, a publiczną stronę obsługuje Cloudflare Worker. Do przyszłych funkcji zapisu (notatki, shortlisty, prywatne tagi i stan oceny) można dodać backend z uwierzytelnieniem oraz Cloudflare D1/SQLite. **D1 nie jest obecnie włączone, a serwis pozostaje tylko do odczytu.**

**Test parsera:** python3 -m unittest discover -s tests -p 'test_catalog.py' -v.
