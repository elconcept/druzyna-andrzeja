# Drużyna Andrzeja

Repozytorium zbiorcze z zależnościami utrzymywanymi jako submoduły Git w katalogu `_vendor/`.

## Start

```bash
git clone https://github.com/elconcept/druzyna-andrzeja.git
cd druzyna-andrzeja
./bootstrap.sh
```

Aby dodać zależność:

```bash
git submodule add https://github.com/OWNER/REPO.git _vendor/REPO
git commit -am "Add REPO submodule"
```

Plik `.gitmodules` jest zarządzany przez `git submodule add`. Skrypt `bootstrap.sh` synchronizuje i aktualizuje wszystkie zarejestrowane submoduły, również zagnieżdżone.
