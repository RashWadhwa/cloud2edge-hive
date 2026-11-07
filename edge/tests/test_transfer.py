import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]


class TransferTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.bundle = Path(cls.directory.name) / "EdgeClimate-Pi.zip"
        subprocess.run([sys.executable, str(ROOT / "scripts/build-transfer.py"),
                        "--output", str(cls.bundle)], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.base = Path(self.directory.name)
        self.target = self.base / "repo"
        self.target.mkdir()
        (self.target / ".git").mkdir()
        (self.target / ".gitignore").write_text("# existing local rules\n.env\n")
        (self.target / "README.md").write_text("User's original readme\n")
        (self.target / ".env").write_text("EXISTING_LOCAL_CONFIG=yes\n")
        (self.target / ".edge/secrets").mkdir(parents=True)
        (self.target / ".edge/secrets/example").write_text("test fixture, not a real credential")
        (self.target / "get-docker.sh").write_text("existing unrelated helper\n")

    def tearDown(self):
        self.directory.cleanup()

    def install(self, *args, bundle=None):
        return subprocess.run([sys.executable, str(bundle or self.bundle), "--target", str(self.target),
                               "--backup-dir", str(self.base / "backups"), *args], capture_output=True, text=True)

    def test_dry_run_does_not_change_files(self):
        result = self.install("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.target / "compose.edge.yml").exists())
        self.assertFalse((self.base / "backups").exists())

    def test_install_preserves_settings_backs_up_source_and_is_repeatable(self):
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.target / ".env").read_text(), "EXISTING_LOCAL_CONFIG=yes\n")
        self.assertEqual((self.target / ".edge/secrets/example").read_text(), "test fixture, not a real credential")
        self.assertEqual((self.target / "get-docker.sh").read_text(), "existing unrelated helper\n")
        ignore = (self.target / ".gitignore").read_text()
        self.assertIn("# existing local rules", ignore)
        self.assertIn("/.edge/", ignore)
        self.assertTrue((self.target / "scripts/edge").stat().st_mode & 0o111)
        backup = next((self.base / "backups").iterdir())
        self.assertEqual((backup / "README.md").read_text(), "User's original readme\n")
        again = self.install()
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertIn("Already installed", again.stdout)

    def test_corrupt_payload_is_rejected_before_changes(self):
        corrupt = self.base / "corrupt.zip"
        with zipfile.ZipFile(self.bundle) as source, zipfile.ZipFile(corrupt, "w") as dest:
            for name in source.namelist():
                data = b"corrupt" if name == "payload/compose.edge.yml" else source.read(name)
                dest.writestr(name, data)
        result = self.install(bundle=corrupt)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Checksum mismatch", result.stderr)
        self.assertFalse((self.target / "compose.edge.yml").exists())

    def test_symlink_destination_is_rejected(self):
        outside = self.base / "outside"
        outside.mkdir()
        (self.target / "edge").symlink_to(outside, target_is_directory=True)
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse((self.target / "compose.edge.yml").exists())

    def test_bundle_contains_only_allowlisted_source(self):
        with zipfile.ZipFile(self.bundle) as bundle:
            manifest = json.loads(bundle.read("manifest.json"))
            for path in manifest["files"]:
                self.assertNotIn(".edge", Path(path).parts)
                self.assertNotIn(".git", Path(path).parts)
                self.assertNotEqual(path, ".env")
                self.assertNotIn("__pycache__", Path(path).parts)
            self.assertIn("scripts/edge", manifest["files"])


if __name__ == "__main__":
    unittest.main()
