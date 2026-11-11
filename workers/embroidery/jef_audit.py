"""Independent binary checks and pyembroidery rereading; no SVG simulation."""
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import struct

from PIL import Image, ImageDraw
import pyembroidery as pe

from process_runner import WorkerFailure

UNITS_PER_MM = 10
PREVIEW_SIZE = 1400
MARGIN = 30


def binary_commands(data):
    if len(data) < 116:
        raise ValueError("JEF header is truncated")
    offset = struct.unpack_from("<I", data)[0]
    colors, records, hoop = struct.unpack_from("<III", data, 24)
    if colors < 1 or offset < 116 + 8 * colors or offset + 2 * records != len(data):
        raise ValueError("JEF table/offset/record length is inconsistent")
    cursor, events, counts = offset, [], Counter()
    x = y = 0
    while cursor < len(data):
        first, second = data[cursor:cursor + 2]
        cursor += 2
        if first == 0x80 and second == 0x10:
            if cursor != len(data):
                raise ValueError("JEF data after END")
            events.append(["end", x, y])
            counts["end"] += 1
            return {"offset": offset, "records_2bytes": records, "hoop_code": hoop,
                    "thread_entries": colors, "counts": dict(counts), "events_01mm": events}
        command = "stitch"
        if first == 0x80:
            if second not in (1, 2) or cursor + 2 > len(data):
                raise ValueError("Unknown/truncated JEF control")
            command = "jump" if second == 2 else "color_change"
            first, second = data[cursor:cursor + 2]
            cursor += 2
        x += first if first < 128 else first - 256
        y -= second if second < 128 else second - 256
        counts[command] += 1
        events.append([command, x, y])
    raise ValueError("Missing JEF END")


def measure(pattern, raw):
    stitches = [s for s in pattern.stitches if s[2] & pe.COMMAND_MASK == pe.STITCH]
    if not stitches or not all(math.isfinite(v) for s in pattern.stitches for v in s[:2]):
        raise ValueError("Empty or nonfinite stitch plan")
    counts = Counter(s[2] & pe.COMMAND_MASK for s in pattern.stitches)
    if counts[pe.STITCH] != raw["counts"].get("stitch", 0):
        raise ValueError("Independent needle counts disagree")
    stitches_by_block = [0]
    for command, _, _ in raw["events_01mm"]:
        if command == "stitch":
            stitches_by_block[-1] += 1
        elif command == "color_change":
            stitches_by_block.append(0)
    if any(count == 0 for count in stitches_by_block) or len(stitches_by_block) != raw["thread_entries"]:
        raise ValueError(f"Empty or unmatched thread blocks: needle stitches per block={stitches_by_block}, "
                         f"thread entries={raw['thread_entries']}")
    xs, ys = [s[0] / UNITS_PER_MM for s in stitches], [s[1] / UNITS_PER_MM for s in stitches]
    return {"width_mm": max(xs) - min(xs), "height_mm": max(ys) - min(ys),
            "stitch_bounds_mm": [min(xs), min(ys), max(xs), max(ys)],
            "needle_stitches": counts[pe.STITCH], "thread_blocks": len(pattern.threadlist),
            "needle_stitches_by_thread_block": stitches_by_block,
            "color_changes": counts[pe.COLOR_CHANGE], "raw_jump_commands": raw["counts"].get("jump", 0),
            "displacement_jump_commands": counts[pe.JUMP], "interpreted_trims": counts[pe.TRIM],
            "end_commands": counts[pe.END], "hoop_code": raw["hoop_code"],
            "count_method": "pyembroidery 1.5.1: trims=True,trim_at=3,trim_distance=None,clipping=True; STITCH endpoint bounds; native coordinates /10 to mm",
            "physical_trim_execution_verified": False}


def render(pattern, bounds, destination):
    left, top, right, bottom = [n * UNITS_PER_MM for n in bounds]
    scale = (PREVIEW_SIZE - 2 * MARGIN) / max(right - left, bottom - top, 1)
    size = (max(1, round((right - left) * scale)) + 2 * MARGIN,
            max(1, round((bottom - top) * scale)) + 2 * MARGIN)
    image = Image.new("RGB", size, "white")
    draw, previous, thread = ImageDraw.Draw(image), (0, 0), 0
    def point(p):
        return ((p[0] - left) * scale + MARGIN, (p[1] - top) * scale + MARGIN)
    for stitch in pattern.stitches:
        command = stitch[2] & pe.COMMAND_MASK
        if command == pe.STITCH:
            color = pattern.threadlist[min(thread, len(pattern.threadlist) - 1)].hex_color()
            draw.line((point(previous), point(stitch)), fill=color, width=2)
        elif command == pe.COLOR_CHANGE:
            thread += 1
        previous = stitch
    image.save(destination)


def audit(directory):
    directory = Path(directory)
    data = (directory / "output.jef").read_bytes()
    try:
        raw = binary_commands(data)
        pattern = pe.read(str(directory / "output.jef"), settings={"trims": True, "trim_at": 3, "trim_distance": None, "clipping": True})
        metrics = measure(pattern, raw)
        render(pattern, metrics["stitch_bounds_mm"], directory / "preview.png")
    except (ValueError, IndexError, struct.error, TypeError) as exc:
        raise WorkerFailure("JEF_INVALID", "reread_failed", {"message": str(exc)}) from exc
    normalized = json.dumps(raw["events_01mm"], separators=(",", ":")).encode()
    (directory / "raw-commands.json").write_bytes(normalized + b"\n")
    metrics.update(jef_sha256=hashlib.sha256(data).hexdigest(), byte_size=len(data),
                   normalized_commands_sha256=hashlib.sha256(normalized).hexdigest())
    return metrics
