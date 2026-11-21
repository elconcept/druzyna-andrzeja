# PolishLawLLM Benchmark — integracja

Repo autora: https://github.com/PiotrTyrakowski/PolishLawLLM-Benchmark
Przypięty SHA: 52d35edc0cdf0f77dd554e0bc84db7c7e9ca43c6.

## Obecny stan

- Smoke: GitHub Actions pobiera kod do tymczasowego katalogu runnera, kompiluje i uruchamia testy metryki exact match. Test nie wywołuje LLM i nie przedstawia wyniku jakości.
- Evaluate: ręczny tryb uruchamia model wyłącznie po sprawdzeniu danych JSONL, korpusów aktów prawnych i sekretu API. Wyniki surowe i oryginalne metryki trzyma jako artefakt przez 7 dni.
- Firebase: niepodłączone. Upstream ma uploader Firestore i frontend Next.js z zapytaniami przez Firebase Admin SDK.
- Licencja: brak deklarowanego LICENSE w upstream; kodu nie publikujemy jako kopii w _workbench.

## Brakujące elementy

1. Zweryfikowane pytania JSONL: benchmarks/tasks/exams/<rok>/<typ>.jsonl lub benchmarks/tasks/judgments/... z pochodzeniem i prawidłowymi odpowiedziami.
2. Historyczne korpusy prawne: benchmarks/corpuses/<rok>/*.json, aby uruchomić oryginalną metrykę TF-IDF ROUGE.
3. Sekrety GitHub Actions: OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, OPENROUTER_API_KEY. Subskrypcje aplikacji web nie są tożsame z płatnym API.
4. Limit kosztów, wielkości próby, czasu i tokenów oraz pełna identyfikacja modelu i daty stanu prawnego.
5. Do dashboardu: projekt Firebase, Firestore, konto serwisowe z minimalnymi uprawnieniami, właściwe reguły bazy, deployment serwera Next.js. Same GitHub Pages nie obsłużą backendu Next.js.

**Ważne:** nie przenosić przykładowych reguł Firestore z upstream do produkcji. Są nieodpowiednie do publicznego systemu zapisu.

Workflow: https://github.com/elconcept/druzyna-andrzeja/actions/workflows/benchmark-polishlawllm.yml

Kod pozostaje w repozytorium GitHub. Artefakty Actions przechowują surowe wyniki chwilowo; Firestore mógłby przechowywać agregaty. W benchmarku rejestrować SHA upstream, hash danych, model, provider, prompty, odpowiedzi, czas, tokeny, koszt, błędy formatu, poprawność odpowiedzi i podstawy prawnej.
