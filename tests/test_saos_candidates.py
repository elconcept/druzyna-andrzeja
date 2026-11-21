"""Local SQLite fixtures for SAOS candidate selection; no external network."""
import json
import sqlite3
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import saos_candidates as mod


class SaosCandidatesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dbfile = Path(self.tmp.name) / "saos.sqlite"
        db = sqlite3.connect(self.dbfile)
        db.execute("CREATE TABLE judgments (id INTEGER PRIMARY KEY, court_type TEXT, judgment_date TEXT, data BLOB)")
        self.good = {
            "id": 1, "textContent": "Tekst uzasadnienia " * 100,
            "legalBases": [{"law": "kc", "article": "415"}],
            "courtCases": [{"caseNumber": "I C 12/23"}],
            "referencedRegulations": ["k.c."]
        }
        self.bad = {"id": 2, "textContent": "krótki", "legalBases": []}
        for i, x in [(1, self.good), (2, self.bad)]:
            db.execute("INSERT INTO judgments VALUES (?,?,?,?)",
                       (i, "COMMON", "2023-06-02", zlib.compress(json.dumps(x).encode("utf-8"))))
        db.commit()
        db.close()

    def tearDown(self):
        self.tmp.cleanup()

    def test_open_database_read_only(self):
        with mod.open_read_only(self.dbfile) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM judgments").fetchone()[0], 2)
            with self.assertRaises(sqlite3.OperationalError):
                con.execute("INSERT INTO judgments VALUES (3,'COMMON','2024',X'00')")

    def test_sample_hashes_without_raw_text(self):
        with mod.open_read_only(self.dbfile) as db:
            rows, counts = mod.sample(db, 0, 1, 300, False, 10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["label_status"], "unverified_no_gold")
        self.assertNotIn("text_content", rows[0])
        self.assertEqual(rows[0]["case_numbers"], ["I C 12/23"])
        self.assertEqual(rows[0]["source_id"], 1)
        self.assertEqual(counts["selected"], 1)

    def test_full_text_explicit(self):
        with mod.open_read_only(self.dbfile) as db:
            rows, audit = mod.sample(db, 0, 2, 300, True, 10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["text_content"], self.good["textContent"])
        self.assertEqual(rows[0]["legal_bases_unverified"], self.good["legalBases"])
        self.assertEqual(audit["skipped"], 1)

    def test_bad_compressed_blob_cannot_break_all(self):
        with sqlite3.connect(self.dbfile) as db:
            db.execute("INSERT INTO judgments VALUES (3,'COMMON','2024',X'01')")
        with mod.open_read_only(self.dbfile) as db:
            rows, audit = mod.sample(db, 0, 2, 300, False, 10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(audit["decode_errors"], 1)


if __name__ == "__main__":
    unittest.main()
