"""Offline tests for the catalog extractor; no network or GitHub token needed."""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import catalog


class CatalogTests(unittest.TestCase):
    SAMPLE = """# Awesome
## Contents
- [Jump](#something)
## Open Source
- [Alpha](https://github.com/Org/Repo) - **[Open Source]** Example project.
- [Alpha again](https://github.com/Org/Repo/) - duplicate from another section.
### MCP Servers
- [Beta](https://example.org/beta) - A hosted service.
## Deprecated / Archived
- [Old](https://github.com/Org/old-repo) - historical software.
"""

    def test_primary_entries_and_no_toc(self):
        items = catalog.parse_readme(self.SAMPLE, "test")
        self.assertEqual(len(items), 4)
        self.assertEqual(items[0]["name"], "Alpha")
        self.assertEqual(items[0]["tags"], ["Open Source", "Prawo polskie"])
        self.assertEqual(items[1]["url"], items[0]["url"])
        self.assertNotIn("#something", [item["url"] for item in items])

    def test_flat_tags_and_archived(self):
        items = catalog.parse_readme(self.SAMPLE, "test")
        self.assertIn("MCP Servers", items[2]["tags"])
        self.assertFalse(items[2]["github"])
        self.assertIn("Archived", items[3]["tags"])
        self.assertTrue(items[3]["github"])

    def test_urls_normalize_and_deduplicate(self):
        a = catalog.normalize_url("https://github.com/Org/Repo/")
        b = catalog.normalize_url("https://github.com/org/repo.git")
        self.assertEqual(a, b)
        self.assertEqual(catalog.github_repo(a), ("org", "repo"))
        self.assertIsNone(catalog.github_repo("https://example.com/service"))

    def test_commercial_archived_tags(self):
        sample = "## Narzędzia\n- [Polska](https://github.com/Org/repo) - aplikacja."
        commercial = catalog.parse_readme(sample, "polskie-legaltech-komercyjne")
        archived = catalog.parse_readme(sample, "polskie-legaltech-archiwum")
        self.assertIn("Prawo polskie", commercial[0]["tags"])
        self.assertIn("Komercyjne", commercial[0]["tags"])
        self.assertIn("Archiwalne", archived[0]["tags"])

    def test_no_foreign_only_legal_standard(self):
        sample = "## Standardy\n- [Akoma Ntoso](https://docs.oasis-open.org/legaldocml/akn-core/v1.0/akn-core-v1.0-part1-vocabulary.html) - international-only."
        self.assertEqual(catalog.parse_readme(sample, "polskie-legaltech-otwarte"), [])

    def test_polish_scope_sources(self):
        feeds = catalog.read_feeds()
        self.assertEqual(len(feeds), 3)
        self.assertTrue(all("awesome-legaltech-pl" in f["url"] for f in feeds))

    def test_repository_score_is_transparent_and_bounded(self):
        at = dt.datetime(2026, 11, 21, tzinfo=dt.timezone.utc)
        metrics = {
            "stars": 70,
            "forks": 12,
            "contributors": 5,
            "last_commit": "2026-11-19T10:00:00Z",
            "license": "MIT",
            "archived": False,
        }
        active = catalog.score_repo(metrics, at)
        self.assertIsNotNone(active)
        self.assertEqual(active["method"], "repo-health-v1")
        self.assertGreater(active["value"], 40)
        self.assertLessEqual(active["value"], 100)
        archived = catalog.score_repo({**metrics, "archived": True}, at)
        self.assertLess(archived["value"], active["value"])
        inactive = catalog.score_repo({**metrics, "last_commit": "2021-01-01T00:00:00Z"}, at)
        self.assertLess(inactive["value"], active["value"])

    def test_missing_metrics_dont_produce_invented_score(self):
        at = dt.datetime(2026, 11, 21, tzinfo=dt.timezone.utc)
        self.assertIsNone(catalog.score_repo({}, at))
        self.assertIsNone(catalog.score_repo({"stars": 2}, at))
        self.assertIsNone(catalog.score_repo({"stars": 3, "last_commit": "invalid"}, at))

    def test_polish_categories_from_source_headings(self):
        sample = "## Źródła prawa i orzecznictwo\n### Serwery MCP\n- [PL](https://github.com/law/repo) - Polish law."
        item = catalog.parse_readme(sample, "polskie-legaltech-otwarte")[0]
        self.assertEqual(item["category"], "Źródła prawa i orzecznictwo")
        self.assertEqual(item["subcategory"], "Serwery MCP")

    def test_reject_bad_urls(self):
        with self.assertRaises(ValueError):
            catalog.normalize_url("file:///etc/passwd")
        with self.assertRaises(ValueError):
            catalog.normalize_url("javascript:alert(1)")


if __name__ == "__main__":
    unittest.main()
