from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from seedvr_studio.updater import check_for_updates


@unittest.skipUnless(shutil.which("git"), "Git is required for updater integration tests")
class UpdaterIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.origin = self.root / "origin"
        self.installation = self.root / "installation"
        self._git("init", "--initial-branch=main", str(self.origin))
        self._git("-C", str(self.origin), "config", "user.email", "updater-test@example.invalid")
        self._git("-C", str(self.origin), "config", "user.name", "Updater Test")
        (self.origin / "app.txt").write_text("version one\n", encoding="utf-8")
        (self.origin / "pyproject.toml").write_text("[project]\nname = \"test-one\"\n", encoding="utf-8")
        origin_scripts = self.origin / "scripts"
        origin_scripts.mkdir()
        shutil.copy2(Path(__file__).resolve().parents[1] / "scripts" / "update.ps1", origin_scripts / "update.ps1")
        (self.origin / ".gitignore").write_text("models/\noutputs/\n", encoding="utf-8")
        self._git("-C", str(self.origin), "add", ".")
        self._git("-C", str(self.origin), "commit", "-m", "Initial")
        self._git("clone", "--quiet", str(self.origin), str(self.installation))

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    @staticmethod
    def _git(*arguments: str) -> None:
        subprocess.run(
            [shutil.which("git") or "git", *arguments],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

    def test_reports_clean_main_as_current(self) -> None:
        status = check_for_updates(self.installation)
        self.assertTrue(status["supported"])
        self.assertFalse(status["update_available"])

    def test_reports_fast_forward_update(self) -> None:
        (self.origin / "app.txt").write_text("version two\n", encoding="utf-8")
        self._git("-C", str(self.origin), "add", "app.txt")
        self._git("-C", str(self.origin), "commit", "-m", "Update")
        status = check_for_updates(self.installation)
        self.assertTrue(status["supported"])
        self.assertTrue(status["update_available"])
        self.assertNotEqual(status["current_version"], status["latest_version"])

    @unittest.skipUnless(shutil.which("powershell.exe"), "Windows PowerShell is required")
    def test_windows_updater_fast_forwards_and_preserves_local_data(self) -> None:
        models = self.installation / "models"
        models.mkdir()
        sentinel = models / "keep.bin"
        sentinel.write_bytes(b"model data")
        (self.origin / "app.txt").write_text("version two\n", encoding="utf-8")
        self._git("-C", str(self.origin), "add", "app.txt")
        self._git("-C", str(self.origin), "commit", "-m", "Update")
        subprocess.run(
            [shutil.which("powershell.exe") or "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", str(self.installation / "scripts" / "update.ps1"), "-ServerProcessId", "999999"],
            cwd=self.installation,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        self.assertEqual((self.installation / "app.txt").read_text(encoding="utf-8"), "version two\n")
        self.assertEqual(sentinel.read_bytes(), b"model data")

    @unittest.skipUnless(shutil.which("powershell.exe"), "Windows PowerShell is required")
    def test_windows_updater_rolls_back_after_dependency_failure(self) -> None:
        models = self.installation / "models"
        models.mkdir()
        sentinel = models / "keep.bin"
        sentinel.write_bytes(b"model data")
        (self.origin / "app.txt").write_text("version two\n", encoding="utf-8")
        (self.origin / "pyproject.toml").write_text("[project]\nname = \"test-two\"\n", encoding="utf-8")
        self._git("-C", str(self.origin), "add", "app.txt", "pyproject.toml")
        self._git("-C", str(self.origin), "commit", "-m", "Dependency update")
        result = subprocess.run(
            [shutil.which("powershell.exe") or "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", str(self.installation / "scripts" / "update.ps1"), "-ServerProcessId", "999999"],
            cwd=self.installation,
            input="\n",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.installation / "app.txt").read_text(encoding="utf-8"), "version one\n")
        self.assertEqual(sentinel.read_bytes(), b"model data")
    def test_refuses_tracked_local_changes(self) -> None:
        (self.installation / "app.txt").write_text("locally edited\n", encoding="utf-8")
        status = check_for_updates(self.installation)
        self.assertFalse(status["supported"])
        self.assertIn("local changes", str(status["message"]))


if __name__ == "__main__":
    unittest.main()
