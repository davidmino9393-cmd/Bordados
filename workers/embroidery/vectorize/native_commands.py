"""Attach native Ink/Stitch endpoint markers in document millimetres.

Format verified against Ink/Stitch v3.2.2 lib/commands.py: target coordinates
come from the marker's x/y, and the hidden connector identifies its object.
"""
import xml.etree.ElementTree as ET

INKSCAPE = "http://www.inkscape.org/namespaces/inkscape"
XLINK = "http://www.w3.org/1999/xlink"
COMMANDS = ("starting_point", "ending_point")


def add_endpoint_commands(root, node, entry=None, exit_point=None):
    root.set("xmlns:inkscape", INKSCAPE)
    root.set("xmlns:xlink", XLINK)
    defs = next((element for element in root if element.tag.split("}")[-1] == "defs"), None)
    if defs is None:
        defs = ET.SubElement(root, "defs")
    existing = {element.get("id") for element in defs}
    for command, point in zip(COMMANDS, (entry, exit_point)):
        if point is None:
            continue
        symbol_id = "inkstitch_" + command
        if symbol_id not in existing:
            symbol = ET.SubElement(defs, "symbol", {"id": symbol_id})
            ET.SubElement(symbol, "circle", {"r": "0.2", "fill": "#008000" if command == COMMANDS[0] else "#ff0000"})
        _attach(root, node.get("id"), command, point)


def add_command(root, node, command, point):
    """Attach one native command that native routing must keep (fill and route ends)."""
    root.set("xmlns:inkscape", INKSCAPE)
    root.set("xmlns:xlink", XLINK)
    defs = next((element for element in root if element.tag.split("}")[-1] == "defs"), None)
    if defs is None:
        defs = ET.SubElement(root, "defs")
    symbol_id = "inkstitch_" + command
    if symbol_id not in {element.get("id") for element in defs}:
        symbol = ET.SubElement(defs, "symbol", {"id": symbol_id})
        ET.SubElement(symbol, "circle", {"r": "0.2"})
    _attach(root, node.get("id"), command, point).set("data-native-command", "keep")


def _attach(root, object_id, command, point):
    x, y = map(float, point)
    marker_id = f"{object_id}_{command}"
    group = ET.SubElement(root, "g", {"id": marker_id + "_group", "inkscape:label": f"Ink/Stitch: {command}"})
    ET.SubElement(group, "path", {
        "id": marker_id + "_connector", "d": f"M{x:.6f},{y:.6f} L{x:.6f},{y:.6f}",
        "style": "display:none", "inkscape:connection-start": "#" + marker_id,
        "inkscape:connection-end": "#" + object_id, "inkscape:connector-type": "polyline",
    })
    ET.SubElement(group, "use", {"id": marker_id, "xlink:href": "#inkstitch_" + command,
                                 "x": f"{x:.6f}", "y": f"{y:.6f}", "width": "100%", "height": "100%"})
    return group
