from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "scripts" / "bootstrap_update.ps1"
POWERSHELL = shutil.which("powershell.exe")
GIT = shutil.which("git")


@unittest.skipUnless(POWERSHELL and GIT, "Windows PowerShell and Git are required")
class BootstrapUpdaterIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.origin = self.root / "origin"
        self.installation = self.root / "installation"
        self.origin.mkdir()
        self.installation.mkdir()
        self._git("init", "--initial-branch=main", str(self.origin))
        self._git("-C", str(self.origin), "config", "user.email", "bootstrap-test@example.invalid")
        self._git("-C", str(self.origin), "config", "user.name", "Bootstrap Test")

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def _git(*arguments: str) -> str:
        result = subprocess.run(
            [GIT or "git", *arguments], check=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True,
        )
        return result.stdout.strip()

    def _write_release(self, repair_exit: int = 0, requirement: str = "same") -> None:
        files = {
            "Launch SeedVR Studio Pro.bat": "@echo off\necho launch\n",
            "api_server.py": "VERSION = 'new'\n",
            "scripts/install.ps1": f"exit {repair_exit}\n",
            "scripts/update.ps1": "Write-Host 'updater'\n",
            "scripts/launch_js.ps1": "Write-Host 'launch'\n",
            "pyproject.toml": f"[project]\nname='seedvr-test'\nversion='{requirement}'\n",
            ".gitignore": ".venv/\noutputs/\nmodels/\ntensorrt_backend/artifacts/\n",
            "web/app.js": "console.log('new');\n",
            "web/index.html": "<html>new</html>\n",
            "seedvr_studio/updater.py": "SUPPORTED = True\n",
            "README.md": "new release\n",
            "requirements-windows-cu130.txt": "same\n",
            "requirements-tensorrt.txt": "same\n",
            "vendor/seedvr2/requirements.txt": "same\n",
        }
        for relative, value in files.items():
            target = self.origin / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(value, encoding="utf-8")
        self._git("-C", str(self.origin), "add", ".")
        self._git("-C", str(self.origin), "commit", "-m", "Release")

    def _write_old_installation(self, requirement: str = "same") -> None:
        files = {
            "Launch SeedVR Studio Pro.bat": "@echo off\necho old launch\n",
            "api_server.py": "VERSION = 'old'\n",
            "scripts/install.ps1": "exit 0\n",
            "pyproject.toml": f"[project]\nname='seedvr-test'\nversion='{requirement}'\n",
            "requirements-windows-cu130.txt": "same\n",
            "requirements-tensorrt.txt": "same\n",
            "vendor/seedvr2/requirements.txt": "same\n",
            "Update SeedVR Studio.bat": "downloaded bootstrap\n",
        }
        for relative, value in files.items():
            target = self.installation / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(value, encoding="utf-8")
        preserved = {
            "models/keep.bin": b"model",
            "tensorrt_backend/artifacts/keep.rtxplan": b"engine",
            "outputs/keep.mp4": b"output",
            ".venv/keep.txt": b"environment",
        }
        for relative, value in preserved.items():
            target = self.installation / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(value)

    def _run(self, skip_repair: bool) -> subprocess.CompletedProcess[str]:
        command = [
            POWERSHELL or "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", str(BOOTSTRAP), "-StudioRoot", str(self.installation),
            "-RepositoryUrl", str(self.origin), "-NoLaunch",
        ]
        if skip_repair:
            command.append("-SkipDependencyRepair")
        return subprocess.run(command, cwd=self.installation, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    def test_zip_migration_preserves_local_data(self) -> None:
        self._write_release()
        self._write_old_installation()
        result = self._run(skip_repair=True)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertTrue((self.installation / ".git").is_dir())
        self.assertEqual((self.installation / "api_server.py").read_text(encoding="utf-8"), "VERSION = 'new'\n")
        self.assertEqual(self._git("-C", str(self.installation), "branch", "--show-current"), "main")
        self.assertEqual(self._git("-C", str(self.installation), "status", "--porcelain", "--untracked-files=no"), "")
        for relative in ("models/keep.bin", "tensorrt_backend/artifacts/keep.rtxplan", "outputs/keep.mp4", ".venv/keep.txt"):
            self.assertTrue((self.installation / relative).is_file())
        self.assertTrue((self.installation / "Update SeedVR Studio.bat").is_file())
        self.assertTrue(any((self.installation / "outputs").glob("bootstrap-backup-*")))

    def test_existing_git_installation_fast_forwards_and_preserves_untracked_data(self) -> None:
        self._write_release()
        shutil.rmtree(self.installation)
        self._git("clone", "--quiet", str(self.origin), str(self.installation))
        (self.installation / "Update SeedVR Studio.bat").write_text("downloaded bootstrap\n", encoding="utf-8")
        (self.installation / "models").mkdir()
        (self.installation / "models" / "keep.bin").write_bytes(b"model")
        (self.origin / "api_server.py").write_text("VERSION = 'newer'\n", encoding="utf-8")
        self._git("-C", str(self.origin), "add", "api_server.py")
        self._git("-C", str(self.origin), "commit", "-m", "Bug fix")

        result = self._run(skip_repair=True)

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(
            (self.installation / "api_server.py").read_text(encoding="utf-8"),
            "VERSION = 'newer'\n",
        )
        self.assertEqual(self._git("-C", str(self.installation), "status", "--porcelain", "--untracked-files=no"), "")
        self.assertEqual((self.installation / "models" / "keep.bin").read_bytes(), b"model")
        self.assertTrue((self.installation / "Update SeedVR Studio.bat").is_file())

    def test_failed_repair_restores_zip_installation(self) -> None:
        self._write_release(repair_exit=7, requirement="changed")
        self._write_old_installation(requirement="old")
        result = self._run(skip_repair=False)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("Dependency refresh failed", result.stdout)
        self.assertIn("Previous application code restored", result.stdout)
        self.assertFalse((self.installation / ".git").exists())
        self.assertEqual((self.installation / "api_server.py").read_text(encoding="utf-8"), "VERSION = 'old'\n")
        self.assertTrue((self.installation / "models/keep.bin").is_file())
        self.assertTrue((self.installation / "outputs/keep.mp4").is_file())
        self.assertTrue((self.installation / "Update SeedVR Studio.bat").is_file())


if __name__ == "__main__":
    unittest.main()
