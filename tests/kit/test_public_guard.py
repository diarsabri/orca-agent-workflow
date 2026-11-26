import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("public_guard", ROOT / "scripts/scan_public.py")
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class PublicationGuardTests(unittest.TestCase):
    def test_detects_material_without_echoing_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            secret = "ghp_" + "A" * 36
            (root / "accident.txt").write_text(secret)
            errors = guard.scan(root)
            self.assertTrue(errors)
            self.assertNotIn(secret, "\n".join(errors))

    def test_synthetic_paths_are_allowed_and_personal_paths_flagged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "note.md"
            path.write_text("/home/example/project")
            self.assertEqual(guard.scan(root), [])
            path.write_text("/" + "Users/actual-person/project")
            self.assertIn("personal macOS path", "\n".join(guard.scan(root)))


if __name__ == "__main__":
    unittest.main()
