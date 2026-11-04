"""Minimal process and binary-audit checks; no original pipeline scripts run."""
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
TEST_TMP = ROOT / "tests" / "engine" / ".tmp"
TEST_TMP.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT / "workers" / "embroidery"))
from process_runner import WorkerFailure, run_logged
from worker import prepared_input, with_hoop_code


class WorkerTests(unittest.TestCase):
    def test_invalid_svg_is_controlled_before_execution(self):
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as tmp:
            with self.assertRaises(WorkerFailure) as caught:
                prepared_input(ROOT / "tests/engine/fixtures/invalid.svg", Path(tmp))
            self.assertEqual(caught.exception.issue["code"], "INPUT_UNREADABLE")

    def test_missing_binary_is_controlled_and_logged(self):
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as tmp:
            with self.assertRaises(WorkerFailure) as caught:
                run_logged([str(Path(tmp) / "absent.exe")], tmp, "missing", 1)
            self.assertEqual(caught.exception.issue["code"], "WORKER_EXPORT_FAILED")
            self.assertTrue((Path(tmp) / "missing.process.json").exists())
            if sys.platform == "win32":
                with patch("windows_job.WindowsJob", side_effect=OSError("injected constructor failure")):
                    with self.assertRaises(WorkerFailure) as aborted:
                        run_logged([sys.executable, "-c", "import time; time.sleep(30)"], tmp, "constructor", 1)
                self.assertTrue(aborted.exception.issue["evidence"]["startup_parent_terminated"])

    def test_timeout_stops_real_process(self):
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as tmp:
            with self.assertRaises(WorkerFailure) as caught:
                code = "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)); time.sleep(30)"
                run_logged([sys.executable, "-c", code], tmp, "timeout", 1)
            self.assertEqual(caught.exception.issue["code"], "WORKER_TIMEOUT")
            self.assertIn("cleanup", caught.exception.issue["evidence"])
            if sys.platform == "win32":
                self.assertTrue(caught.exception.issue["evidence"]["cleanup"]["confirmed"])
                self.assertGreaterEqual(caught.exception.issue["evidence"]["cleanup"]["total_processes"], 2)

    def test_exit_zero_with_no_payload_is_not_success(self):
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as tmp:
            with self.assertRaises(WorkerFailure) as caught:
                run_logged([sys.executable, "-c", "pass"], tmp, "empty", 5)
            self.assertEqual(caught.exception.issue["reason"], "nonzero_exit_or_empty_payload")

    def test_the_header_hoop_code_follows_the_profile_and_nothing_else_in_the_file_changes(self):
        original = (ROOT / "Anime_Socks_Bordado_13x12/Anime_Socks_13x12.jef").read_bytes()  # el exportador le puso código 2 (140 x 200)
        before = struct.unpack_from("<I", original, 32)[0]
        self.assertNotEqual(before, 4)
        patched, change = with_hoop_code(original, 4)
        self.assertEqual(struct.unpack_from("<I", patched, 32)[0], 4)
        self.assertEqual((patched[:32], patched[36:]), (original[:32], original[36:]))
        self.assertEqual((change["field"], change["from"], change["to"]), ("hoop_code", before, 4))
        from jef_audit import binary_commands
        self.assertEqual(binary_commands(patched)["hoop_code"], 4)  # el lector independiente ve el código nuevo
        self.assertEqual(binary_commands(patched)["records_2bytes"], binary_commands(original)["records_2bytes"])

    def test_a_truncated_header_cannot_take_a_hoop_code(self):
        with self.assertRaises(WorkerFailure) as caught:
            with_hoop_code(b"\x00" * 20, 4)
        self.assertEqual(caught.exception.issue["code"], "JEF_INVALID")

    def test_reader_cannot_hide_missing_or_invalid_end(self):
        from jef_audit import binary_commands
        data = (ROOT / "Anime_Socks_Bordado/Anime_Socks_Optimizado.jef").read_bytes()
        missing_end = bytearray(data[:-2])
        records = struct.unpack_from("<I", data, 28)[0]
        struct.pack_into("<I", missing_end, 28, records - 1)
        unknown = bytearray(data)
        offset = struct.unpack_from("<I", data)[0]
        unknown[offset:offset + 2] = b"\x80\x7f"
        for invalid in (missing_end, unknown):
            with self.subTest(invalid=invalid[-2:]), self.assertRaises(ValueError):
                binary_commands(invalid)


if __name__ == "__main__":
    unittest.main()
