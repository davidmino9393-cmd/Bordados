"""Routing opt-in, color order, endpoint markers and native rung regression."""
from pathlib import Path
import sys
import tempfile
import unittest
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "workers/embroidery"))
from native_routing import _groups, requested
from native_satin_cleanup import cleanup, SUBPATH
from process_runner import WorkerFailure
from vectorize.native_commands import add_endpoint_commands

SVG = "{http://www.w3.org/2000/svg}"
IS = "{http://inkstitch.org/namespace}"


class NativeRoutingTests(unittest.TestCase):
    def test_routing_requires_explicit_generated_metadata(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests/engine/.tmp") as tmp:
            source = Path(tmp) / "input.svg"
            source.write_text('<svg xmlns="http://www.w3.org/2000/svg"><path d="M0,0 L1,1"/></svg>')
            self.assertFalse(requested(source))
            source.write_text('<svg xmlns="http://www.w3.org/2000/svg"><desc>{"routing":{"native_auto_route":true}}</desc></svg>')
            self.assertTrue(requested(source))

    def test_each_color_keeps_its_fill_before_its_satin(self):
        root = ET.Element(SVG + "svg")
        ET.SubElement(root, SVG + "path", {"id": "preliminary", "data-technique": "hidden_running_connector",
                                           "style": "fill:none;stroke:#00ff00"})
        for color in ("#ff0000", "#0000ff"):
            ET.SubElement(root, SVG + "path", {"id": color[1:] + "s", "data-technique": "satin",
                                               "style": f"fill:none;stroke:{color}", IS + "trim_after": "true"})
            ET.SubElement(root, SVG + "path", {"id": color[1:] + "f", "data-technique": "fill",
                                               "style": f"fill:{color};stroke:none"})
        self.assertEqual(_groups(root), [("native_route_0", "auto_satin"), ("native_route_1", "auto_satin")])
        self.assertFalse(any(p.get("id") == "preliminary" for p in root.iter()))
        for group in root:
            paths = list(group.iter(SVG + "path"))
            self.assertEqual([p.get("data-technique") for p in paths], ["fill", "satin"])
            self.assertNotIn(IS + "trim_after", paths[-1].attrib)

    def test_rung_cleanup_keeps_both_rails_and_the_stitch_recipe(self):
        root = ET.Element(SVG + "svg")
        rails = "M0,0 L5,0 L10,0 M0,2 L5,2 L10,2 "
        node = ET.SubElement(root, SVG + "path", {"id": "satin", "d": rails +
            "M2,-.1 L2,2.1 M5,-.1 L5,2.1 M8,-.1 L8,2.1", IS + "satin_column": "true",
            IS + "zigzag_spacing_mm": ".4", IS + "short_stitch_inset": ".15"})
        before = SUBPATH.findall(node.get("d"))[:2]
        report = cleanup(root)
        after = SUBPATH.findall(node.get("d"))
        self.assertEqual([s.strip() for s in after[:2]], [s.strip() for s in before])
        self.assertEqual(len(after), 3)
        self.assertEqual(report["removed_guides"], 2)
        self.assertTrue(report["rails_preserved"])
        self.assertEqual(node.get(IS + "zigzag_spacing_mm"), ".4")

    def test_unverified_native_geometry_fails_before_export(self):
        root = ET.Element(SVG + "svg")
        ET.SubElement(root, SVG + "path", {"id": "broken", "d": "M0,0 L0,0 M1,0 L1,0",
                                           IS + "satin_column": "true"})
        with self.assertRaises(WorkerFailure) as caught:
            cleanup(root)
        self.assertEqual(caught.exception.issue["reason"], "native_satin_cleanup_unverified")

    def test_optional_start_marker_points_to_target_coordinates(self):
        root = ET.Element("svg")
        node = ET.SubElement(root, "path", {"id": "column"})
        add_endpoint_commands(root, node, entry=(3, 4))
        uses = list(root.iter("use"))
        self.assertEqual(len(uses), 1)
        self.assertEqual((float(uses[0].get("x")), float(uses[0].get("y"))), (3, 4))
        self.assertEqual(uses[0].get("xlink:href"), "#inkstitch_starting_point")
        connector = next(n for n in root.iter("path") if n is not node)
        self.assertEqual(connector.get("inkscape:connection-end"), "#column")
        self.assertEqual(connector.get("style"), "display:none")


if __name__ == "__main__":
    unittest.main()
