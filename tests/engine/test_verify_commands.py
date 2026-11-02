"""Structural checks for normalized raw command evidence."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "workers" / "embroidery"))

from verify_commands import IDENTICAL, compare_raw_commands


class VerifyCommandsTests(unittest.TestCase):
    def write(self, directory, name, commands, newline="\n"):
        path = Path(directory) / name
        text = json.dumps(commands, separators=(",", ":")) + newline
        path.write_bytes(text.encode("utf-8"))
        return path

    def test_identical_commands_are_structural_match(self):
        commands = [["jump", 0, 0], ["stitch", 10, 20], ["end", 10, 20]]
        with tempfile.TemporaryDirectory() as tmp:
            reference = self.write(tmp, "reference.json", commands)
            actual = self.write(tmp, "actual.json", commands)
            report = compare_raw_commands(reference, actual)
        self.assertEqual(report["reference_count"], 3)
        self.assertEqual(report["actual_count"], 3)
        self.assertEqual(report["difference_indices"], [])
        self.assertEqual(report["verdict"], IDENTICAL)

    def test_changed_command_reports_its_index(self):
        reference_commands = [
            ["jump", 0, 0],
            ["stitch", 10, 20],
            ["stitch", 20, 30],
            ["end", 20, 30],
        ]
        actual_commands = list(reference_commands)
        actual_commands[2] = ["stitch", 21, 30]
        with tempfile.TemporaryDirectory() as tmp:
            reference = self.write(tmp, "reference.json", reference_commands)
            actual = self.write(tmp, "actual.json", actual_commands)
            report = compare_raw_commands(reference, actual)
        self.assertEqual(report["first_difference_index"], 2)
        self.assertEqual(report["difference_indices"], [2])
        self.assertEqual(report["verdict"], "DIFERENCIA EN INDICE 2")

    def test_length_difference_reports_both_counts(self):
        reference_commands = [["jump", 0, 0], ["stitch", 10, 20], ["end", 10, 20]]
        actual_commands = reference_commands[:2]
        with tempfile.TemporaryDirectory() as tmp:
            reference = self.write(tmp, "reference.json", reference_commands)
            actual = self.write(tmp, "actual.json", actual_commands)
            report = compare_raw_commands(reference, actual)
        self.assertEqual(report["reference_count"], 3)
        self.assertEqual(report["actual_count"], 2)
        self.assertEqual(report["first_difference_index"], 2)
        self.assertEqual(report["verdict"], "DIFERENCIA EN INDICE 2")

    def test_line_endings_do_not_change_verdict(self):
        commands = [["jump", 0, 0], ["end", 0, 0]]
        with tempfile.TemporaryDirectory() as tmp:
            reference = self.write(tmp, "reference.json", commands, newline="\n")
            actual = self.write(tmp, "actual.json", commands, newline="\r\n")
            report = compare_raw_commands(reference, actual)
        self.assertEqual(report["verdict"], IDENTICAL)


if __name__ == "__main__":
    unittest.main()
