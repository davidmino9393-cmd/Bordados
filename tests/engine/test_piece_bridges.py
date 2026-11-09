"""Component bridges, fill links and per-component native cuts (Order 6)."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "packages/contracts"), str(ROOT / "workers/embroidery")]
from native_routing import _ensure_exit_trims, _groups
from vectorize import piece_bridges
from vectorize.contours import signed_area

SVG = "{http://www.w3.org/2000/svg}"
IS = "{http://inkstitch.org/namespace}"
ENGINE = Path(os.environ.get("EMBROIDERY_INKSTITCH_EXE", str(Path.home() /
              "AppData/Roaming/inkscape/extensions/inkstitch/inkstitch/bin/inkstitch.exe")))
SCALE = 0.1


def ring(x0, y0, x1, y1):
    points = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    points = points if signed_area(points) > 0 else list(reversed(points))
    return "M" + " L".join(f"{x},{y}" for x, y in points) + " Z"


def running(ring_index, *points):
    return {"omitted": None, "technique": "running", "ring_index": ring_index,
            "stitch_path_mm": "M" + " L".join(f"{x},{y}" for x, y in points)}


def fill(ring_index, x0, y0, x1, y1):
    return {"omitted": None, "technique": "fill", "ring_index": ring_index, "fill_path_mm": ring(x0, y0, x1, y1)}


def plan(path, units):
    return piece_bridges.plan(SimpleNamespace(path_data_mm=path), units, SCALE, (0, 0), .25)


class PieceBridgeTests(unittest.TestCase):
    def test_gap_inside_the_stroke_is_bridged_end_to_centre_line(self):
        result = plan(ring(0, 0, 10, 2), [running(0, (0.5, 1), (4, 1)), running(0, (5.5, 1), (9.5, 1))])
        self.assertEqual(set(result["component_of"].values()), {0})
        self.assertEqual(len(result["bridges"]), 1)
        self.assertAlmostEqual(result["bridges"][0]["length_mm"], 1.5)
        self.assertEqual((result["evidence"]["pieces_before"], result["evidence"]["pieces_after"]), (2, 1))

    def test_blank_fabric_is_never_bridged(self):
        path = ring(0, 0, 4, 2) + " " + ring(6, 0, 10, 2)
        result = plan(path, [running(0, (0.5, 1), (3.5, 1)), running(1, (6.5, 1), (9.5, 1))])
        self.assertEqual(len(set(result["component_of"].values())), 2)
        self.assertEqual(result["bridges"], [])

    def test_gap_closed_by_pull_compensation_joins_components_only(self):
        # 0.5 mm blank < 2 x (0.25 pull + 0.05 rounding): same component, still cut-free.
        path = ring(0, 0, 4, 2) + " " + ring(4.5, 0, 8.5, 2)
        result = plan(path, [running(0, (0.5, 1), (3.5, 1)), running(1, (5, 1), (8, 1))])
        self.assertEqual(len(set(result["component_of"].values())), 1)

    def test_long_travel_inside_the_mask_is_not_bridged(self):
        result = plan(ring(0, 0, 20, 2), [running(0, (0.5, 1), (4, 1)), running(0, (9, 1), (19, 1))])
        self.assertEqual(result["bridges"], [])
        self.assertEqual(result["evidence"]["pieces_after"], 2)

    def test_fills_link_through_verified_gap_then_enter_the_stroke_route(self):
        units = [fill(0, 0, 0, 4, 4), fill(0, 4.5, 0, 8.5, 4), running(0, (9, 2), (11.5, 2))]
        result = plan(ring(0, 0, 12, 4), units)
        exits = result["fill_exits"]
        self.assertEqual(result["fill_order"], {0: 0, 1: 1})
        self.assertEqual((exits[0]["kind"], exits[0]["next_unit"]), ("fill_link", 1))
        self.assertAlmostEqual(exits[0]["length_mm"], .5)
        self.assertEqual((exits[1]["kind"], exits[1]["next_unit"]), ("route_start", 2))

    def test_fill_gap_over_blank_fabric_is_cut(self):
        path = ring(0, 0, 4, 4) + " " + ring(6, 0, 10, 4)
        result = plan(path, [fill(0, 0, 0, 4, 4), fill(1, 6, 0, 10, 4)])
        self.assertEqual(result["fill_exits"][0]["kind"], "trim")


class ComponentRoutingTests(unittest.TestCase):
    def node(self, root, node_id, technique, component, **extra):
        style = "fill:#000000;stroke:none" if technique == "fill" else "fill:none;stroke:#000000"
        return ET.SubElement(root, SVG + "path", {"id": node_id, "data-technique": technique, "d": extra.pop("d", "M0,0 L1,0"),
                                                 "data-component": component, "style": style, **extra})

    def test_each_component_is_routed_once_and_cut_at_its_exit(self):
        root = ET.Element(SVG + "svg")
        self.node(root, "far_fill_b", "fill", "o:1", d="M50,0 L51,0", **{"data-fill-order": "1", "data-fill-exit": "trim"})
        self.node(root, "far_fill_a", "fill", "o:1", d="M50,0 L51,0", **{"data-fill-order": "0", "data-fill-exit": "fill_link"})
        self.node(root, "far_satin", "satin", "o:1", d="M50,0 L51,0", **{IS + "trim_after": "true"})
        self.node(root, "near_run", "running", "o:0")
        routes = _groups(root)
        self.assertEqual(routes, [("native_route_1", "auto_satin")])
        components = [g for g in root.iter(SVG + "g") if g.get("id", "").startswith("native_component_")]
        order = [[p.get("id") for p in g.iter(SVG + "path")] for g in components]
        self.assertEqual(order, [["near_run"], ["far_fill_a", "far_fill_b", "far_satin"]])
        by_id = {p.get("id"): p for p in root.iter(SVG + "path")}
        self.assertEqual(by_id["near_run"].get(IS + "trim_after"), "true")
        self.assertIsNone(by_id["far_fill_a"].get(IS + "trim_after"))
        self.assertEqual(by_id["far_fill_b"].get(IS + "trim_after"), "true")
        self.assertIsNone(by_id["far_satin"].get(IS + "trim_after"))
        self.assertEqual(_ensure_exit_trims(root), 1)
        self.assertEqual(by_id["far_satin"].get(IS + "trim_after"), "true")


@unittest.skipUnless(ENGINE.is_file(), "Installed Ink/Stitch required for the auto_satin join probe")
class NativeJoinThresholdTests(unittest.TestCase):
    """Ink/Stitch 3.2.2 joins a stroke end 0.5 mm from a satin centre line, not at 1.0 mm."""

    def trims(self, gap):
        rails = "M10,48.5 L30,48.5 L50,48.5 M10,51.5 L30,51.5 L50,51.5 M16,48.2 L16,51.8"
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkstitch="http://inkstitch.org/namespace" '
               'xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" width="100mm" height="100mm" viewBox="0 0 100 100">'
               '<metadata><inkstitch:inkstitch_svg_version>3</inkstitch:inkstitch_svg_version></metadata>'
               f'<g id="grp" inkscape:groupmode="layer"><path id="s" d="{rails}" style="fill:none;stroke:#000;stroke-width:3" '
               'inkstitch:satin_column="true"/>'
               f'<path id="r" d="M30,20 L30,{50 - gap}" style="fill:none;stroke:#000;stroke-width:0.2" '
               'inkstitch:stroke_method="running_stitch"/></g></svg>')
        with tempfile.TemporaryDirectory(dir=ROOT / "tests/engine/.tmp") as tmp:
            source = Path(tmp) / "probe.svg"
            source.write_text(svg, encoding="utf-8")
            output = subprocess.run([str(ENGINE), "--extension=auto_satin", "--id=grp", "--preserve_order=false",
                                     "--keep_originals=false", "--trim=true", str(source)],
                                    capture_output=True, timeout=120, check=True).stdout.decode()
        return output.count('href="#inkstitch_trim"')

    def test_join_threshold_used_by_bridges(self):
        self.assertEqual(self.trims(piece_bridges.JOIN_MM), 1, "only the exit cut")
        self.assertGreater(self.trims(1.0), 1)


if __name__ == "__main__":
    unittest.main()
