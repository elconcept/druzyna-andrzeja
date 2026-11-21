"""Integration tests using local Git remotes; no network or external packages."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sync.py"


class SynchronizationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.src = base / "source"
        self.root = base / "aggregate"
        for path in (self.src, self.root):
            path.mkdir()
            self.git(path, "init", "-q", "-b", "main")
            self.git(path, "config", "user.email", "test@example.invalid")
            self.git(path, "config", "user.name", "Test")
        (self.src / "main.py").write_text("v1\n")
        (self.src / "omit.txt").write_text("v1\n")
        (self.src / "old.txt").write_text("v1\n")
        (self.src / "LICENSE").write_text("Example License\n")
        (self.src / ".dockerignore").write_text("target/\n")
        (self.src / ".gitignore").write_text("*.tmp\n")
        self.commit_src("first")
        (self.root / "scripts").mkdir()
        shutil.copy2(SCRIPT, self.root / "scripts" / "sync.py")
        self.sources = self.root / "sources.toml"
        self.sources.write_text('version = 1\n[[repo]]\nname = "example"\nurl = "' + self.src.as_uri() + '"\nbranch = "main"\n')
        (self.root / ".gitmodules").touch()
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-qm", "scaffold")
        self.env = os.environ.copy()
        self.env.update({"DRUZYNA_ALLOW_LOCAL_TEST_URLS": "1", "GIT_TERMINAL_PROMPT": "0",
                         "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "protocol.file.allow",
                         "GIT_CONFIG_VALUE_0": "always"})

    def git(self, cwd, *args):
        return subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, check=True).stdout

    def commit_src(self, message):
        self.git(self.src, "add", "-A")
        self.git(self.src, "commit", "-qm", message)

    def sync(self, refresh=True):
        args = [sys.executable, str(self.root / "scripts" / "sync.py")]
        if refresh:
            args.append("--refresh")
        proc = subprocess.run(args, cwd=self.root, env=self.env, text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + "\n" + proc.stderr)

    def test_immutable_vendor_and_modified_workbench(self):
        self.sync()
        wb = self.root / "_workbench" / "example"
        vd = self.root / "_vendor" / "example"
        self.assertEqual((wb / "main.py").read_text(), "v1\n")
        self.assertFalse((wb / "LICENSE").exists())
        self.assertFalse((wb / ".gitignore").exists())
        self.assertFalse((wb / ".dockerignore").exists())
        self.assertFalse((wb / ".git").exists())
        self.assertEqual((self.root / "_licenses" / "example" / "LICENSE").read_text(), "Example License\n")
        self.assertEqual((vd / "main.py").read_text(), "v1\n")
        self.assertEqual(self.git(self.root, "ls-files", "--stage", "_vendor/example").split(" ")[0], "160000")
        self.assertIn("_vendor/example", (self.root / ".gitmodules").read_text())
        wb.joinpath("main.py").write_text("MY EDIT\n")
        wb.joinpath("omit.txt").unlink()
        (self.src / "main.py").write_text("v2\n")
        (self.src / "omit.txt").write_text("v2\n")
        (self.src / "old.txt").unlink()
        (self.src / "new.txt").write_text("new\n")
        self.commit_src("second")
        self.sync()
        self.assertEqual((vd / "main.py").read_text(), "v2\n")
        self.assertEqual((wb / "main.py").read_text(), "MY EDIT\n")
        self.assertFalse((wb / "omit.txt").exists())
        self.assertFalse((wb / "old.txt").exists())
        self.assertEqual((wb / "new.txt").read_text(), "new\n")
        self.assertIn("main.py", (self.root / "_sync" / "last-run.md").read_text())
        self.assertIn("omit.txt", (self.root / "_sync" / "last-run.md").read_text())
        stable_report = (self.root / "_sync" / "last-run.md").read_bytes()
        self.sync()
        self.assertEqual((wb / "main.py").read_text(), "MY EDIT\n")
        self.assertEqual((self.root / "_sync" / "last-run.md").read_bytes(), stable_report)

    def test_fresh_clone_reads_pinned_submodules(self):
        self.sync()
        self.git(self.root, "add", "-A")
        self.git(self.root, "commit", "-qm", "pinned first sync")
        fresh = Path(self.tmp.name) / "fresh-clone"
        self.git(Path(self.tmp.name), "clone", "-q", str(self.root), str(fresh))
        proc = subprocess.run([sys.executable, str(fresh / "scripts" / "sync.py")],
                              cwd=fresh, env=self.env, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual((fresh / "_vendor" / "example" / "main.py").read_text(), "v1\n")
        self.assertEqual((fresh / "_workbench" / "example" / "main.py").read_text(), "v1\n")

    def test_local_collision_does_not_overwrite(self):
        self.sync()
        wb = self.root / "_workbench" / "example"
        (wb / "fresh.py").write_text("LOCAL\n")
        (self.src / "fresh.py").write_text("REMOTE\n")
        self.commit_src("add fresh")
        self.sync()
        self.assertEqual((wb / "fresh.py").read_text(), "LOCAL\n")
        self.assertEqual((self.root / "_vendor" / "example" / "fresh.py").read_text(), "REMOTE\n")

    def test_removed_source_keeps_workbench(self):
        self.sync()
        self.sources.write_text("version = 1\n")
        self.sync(refresh=False)
        self.assertTrue((self.root / "_workbench" / "example" / "main.py").is_file())
        self.assertNotIn("_vendor/example", self.git(self.root, "ls-files", "--stage"))
        self.assertEqual((self.root / ".gitmodules").read_text(), "")

    def test_refuse_dirty_vendor(self):
        self.sync()
        (self.root / "_vendor" / "example" / "main.py").write_text("uncommitted\n")
        cmd = [sys.executable, str(self.root / "scripts" / "sync.py"), "--refresh"]
        proc = subprocess.run(cmd, cwd=self.root, env=self.env, capture_output=True, text=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("lokalne zmiany", proc.stderr)


if __name__ == "__main__":
    unittest.main()
