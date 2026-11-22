"""Damaged persistent chunk boundaries self-heal; failed writes preserve old data."""
import ast
import contextlib
import importlib.util
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("whole_write", ROOT / "nx2/whole_write.py")
whole_write = importlib.util.module_from_spec(spec)
spec.loader.exec_module(whole_write)
# Exercise production functions without importing the full lifter or any game data.
tree = ast.parse((ROOT / "nx2/chunks.py").read_text(encoding="utf-8"))
cuts = ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ("load", "save")], type_ignores=[])
scope = dict(os=os, FILE="chunks.txt", whole_write=whole_write)
exec(compile(cuts, str(ROOT / "nx2/chunks.py"), "exec"), scope)


class ChunkCache(unittest.TestCase):
    def test_valid_and_missing(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(scope["load"](folder), [])
            scope["save"](folder, [0x1008, 0x1000, 0x1008])
            self.assertEqual(scope["load"](folder), [0x1000, 0x1008])

    def test_corruption_and_read_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "chunks.txt"
            for bad in (b"\0" * 688, b"00001000\ntruncated!", b"\xff", b"-4", b"1001", b"1000\n1000", b"1008\n1000"):
                path.write_bytes(bad)
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(scope["load"](folder), [])
            with patch("builtins.open", side_effect=OSError("unreadable")), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(scope["load"](folder), [])

    def test_failed_flush_preserves_previous_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            scope["save"](folder, [0x1000])
            with patch.object(whole_write.os, "fsync", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    scope["save"](folder, [0x2000])
            self.assertEqual(scope["load"](folder), [0x1000])
            scope["save"](folder, [0x3000])
            self.assertEqual(scope["load"](folder), [0x3000])


if __name__ == "__main__":
    unittest.main()
