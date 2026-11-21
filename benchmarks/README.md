# PolishLawLLM Benchmark — integracja

Repo autora: https://github.com/PiotrTyrakowski/PolishLawLLM-Benchmark
Przypięty SHA: 52d35edc0cdf0f77dd554e0bc84db7c7e9ca43c6.

## Obecny stan

- Smoke: GitHub Actions pobiera kod do tymczasowego katalogu runnera, kompiluje i uruchamia testy metryki exact match. Test nie wywołuje LLM i nie przedstawia wyniku jakości.
- Evaluate: ręczny tryb uruchamia model wyłącznie po sprawdzeniu danych JSONL, korpusów aktów prawnych i sekretu API. Wyniki surowe i oryginalne metryki trzyma jako artefakt przez 7 dni.
- Firebase: niepodłączone. Upstream ma uploader Firestore i frontend Next.js z zapytaniami przez Firebase Admin SDK.
- Licencja: brak deklarowanego LICENSE w upstream; kodu nie publikujemy jako kopii w _workbench.

## Istniejące źródła orzeczeń

Manifest: [corpora.toml](corpora.toml).

**SAOS / Synology DS1821+:** /volume2/docker/mcp-saos/data/saos.sqlite (kontener: /data/saos.sqlite).
Plik około 22 GiB, aktywna baza SQLite z WAL. Lokalny status mcp-saos z 2026-11-21:
545 672 orzeczenia, 334/334 okien zweryfikowanych, indexStatus complete.
Baza posiada tabelę judgments i pole data skompresowane zlib/deflate do JSON.
Nie dublować bazy na GitHub; otwierać ją tylko do odczytu.

Zapis małej puli kandydatów na Synology, bez pełnej treści, bez gold labels:

    python3 scripts/saos_candidates.py --db /volume2/docker/mcp-saos/data/saos.sqlite --output /tmp/saos-candidates.jsonl --limit 100

Pełny tekst wymaga jawnej flagi --include-text. Skrypt nie modyfikuje bazy,
nie zmienia trybu WAL i nie kopiuje źródłowych 22 GB.

**Hugging Face / JuDDGES:** https://huggingface.co/datasets/JuDDGES/juddges-pl
Konfiguracje pl-court oraz pl-nsa. Źródło zawiera także orzeczenia
sądów administracyjnych, których lokalny mcp-saos nie indeksuje.
Wyodrębnione przez Gemini 2.5 Pro pola anotacji są SILVER LABELS,
niezweryfikowane osobno dla każdego orzeczenia. Nie używać ich jako
referencyjnych odpowiedzi benchmarku bez osobnej walidacji.
Warstwa wzbogacenia JuDDGES jest CC BY 4.0, orzeczenia mają status materiałów urzędowych.
Zbiór JuDDGES/pl-swiss-franc-loans zawiera zweryfikowane anotacje,
ale ich dopasowanie do zadania maskowania przepisów wymaga sprawdzenia.

Stan: lokalną bazę i próbkę 100 rekordów sprawdzono. Korpus źródłowy
jest dostępny, lecz referencyjny zbiór pytań gold do oceny LLM
nie został jeszcze przygotowany ani podłączony do hosted GitHub Actions.
## Brakujące elementy

1. Zweryfikowane zadania JSONL z odpowiedziami gold (źródłowe orzeczenia są już na NAS): benchmarks/tasks/exams/<rok>/<typ>.jsonl lub benchmarks/tasks/judgments/... z pochodzeniem i prawidłowymi odpowiedziami.
2. Historyczne korpusy prawne: benchmarks/corpuses/<rok>/*.json, aby uruchomić oryginalną metrykę TF-IDF ROUGE.
3. Sekrety GitHub Actions: OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, OPENROUTER_API_KEY. Subskrypcje aplikacji web nie są tożsame z płatnym API.
4. Limit kosztów, wielkości próby, czasu i tokenów oraz pełna identyfikacja modelu i daty stanu prawnego.
5. Do dashboardu: projekt Firebase, Firestore, konto serwisowe z minimalnymi uprawnieniami, właściwe reguły bazy, deployment serwera Next.js. Same GitHub Pages nie obsłużą backendu Next.js.

**Ważne:** nie przenosić przykładowych reguł Firestore z upstream do produkcji. Są nieodpowiednie do publicznego systemu zapisu.

Workflow: https://github.com/elconcept/druzyna-andrzeja/actions/workflows/benchmark-polishlawllm.yml

Kod pozostaje w repozytorium GitHub. Artefakty Actions przechowują surowe wyniki chwilowo; Firestore mógłby przechowywać agregaty. W benchmarku rejestrować SHA upstream, hash danych, model, provider, prompty, odpowiedzi, czas, tokeny, koszt, błędy formatu, poprawność odpowiedzi i podstawy prawnej.
