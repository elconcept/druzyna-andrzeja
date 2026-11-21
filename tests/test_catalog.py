"""Offline tests for the catalog extractor; no network or GitHub token needed."""
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
        self.assertEqual(items[0]["tags"], ["Open Source"])
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

    def test_reject_bad_urls(self):
        with self.assertRaises(ValueError):
            catalog.normalize_url("file:///etc/passwd")
        with self.assertRaises(ValueError):
            catalog.normalize_url("javascript:alert(1)")


if __name__ == "__main__":
    unittest.main()
