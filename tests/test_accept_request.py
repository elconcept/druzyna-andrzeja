"""No-network validation of public fetch requests."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from accept_request import decide

CATALOG={"jurisdiction":"PL","proposals":[{"github":True,"url":"https://github.com/example/test-project"}]}
META={"full_name":"example/test-project","private":False,"archived":False,"size":1500,
      "license":{"spdx_id":"MIT"}}
SOURCE="version = 1\n"


class TestFetchRequests(unittest.TestCase):
    def test_add(self):
        state,message,content=decide({"title":"fetch: example/test-project"},META,CATALOG,SOURCE)
        self.assertEqual(state,"added")
        self.assertIn('name = "example-test-project"',content)
        self.assertIn('url = "https://github.com/example/test-project.git"',content)

    def test_not_approved_source(self):
        state,_,content=decide({"title":"fetch: foreign/repo"},META,CATALOG,SOURCE)
        self.assertEqual(state,"rejected")
        self.assertEqual(content,SOURCE)

    def test_code_injection_rejected(self):
        state,_,content=decide({"title":"fetch: example/test-project; echo bad"},META,CATALOG,SOURCE)
        self.assertEqual(state,"ignored")
        self.assertEqual(content,SOURCE)

    def test_no_license(self):
        state,_,content=decide({"title":"fetch: example/test-project"},
                               {**META,"license":None},CATALOG,SOURCE)
        self.assertEqual(state,"rejected")
        self.assertEqual(content,SOURCE)

    def test_too_big(self):
        state,_,_=decide({"title":"fetch: example/test-project"},
                         {**META,"size":26000},CATALOG,SOURCE)
        self.assertEqual(state,"rejected")

    def test_duplicate(self):
        _,_,updated=decide({"title":"fetch: example/test-project"},META,CATALOG,SOURCE)
        state,_,repeat=decide({"title":"fetch: example/test-project"},META,CATALOG,updated)
        self.assertEqual(state,"already")
        self.assertEqual(repeat,updated)

    def test_renamed_repo(self):
        state,_,_=decide({"title":"fetch: example/test-project"},
                         {**META,"full_name":"other/renamed"},CATALOG,SOURCE)
        self.assertEqual(state,"rejected")

    def test_max_entries(self):
        other="\n".join(f'[[repo]]\nname = "existing{i}"\nurl = "https://github.com/o/x{i}.git"' for i in range(32))
        state,_,_=decide({"title":"fetch: example/test-project"},META,CATALOG,SOURCE+other)
        self.assertEqual(state,"rejected")


if __name__=="__main__":
    unittest.main()
