#!/usr/bin/env python3
"""Compare the Horizon goggles draw path with the pinned Java client readouts."""

import argparse
from collections import defaultdict
import json
from pathlib import Path
from zipfile import ZipFile

from fixture_world import ROOT, fixture_world

COLOR = {
    "gray": 0xAAAAAA, "dark_gray": 0x555555, "green": 0x55FF55, "aqua": 0x55FFFF,
    "red": 0xFF5555, "yellow": 0xFFFF55, "gold": 0xFFAA00, "light_purple": 0xFF55FF,
}
GAUGES = {"speed": (6, 98, -10), "stress": (8, 98, -10)}


def component_styles(component, translation, color=None, strike=False):
    if isinstance(component, str):
        return [(color, strike)] * len(component)
    color = COLOR.get(component.get("color"), color)
    strike = component.get("strikethrough", strike)
    text = (translation[component["translate"]]
            if "translate" in component else component.get("text", ""))
    return ([(color, strike)] * len(text)
            + [style for child in component.get("extra", [])
               for style in component_styles(child, translation, color, strike)])


def expected_readouts(fixture):
    with ZipFile(ROOT / ".local/create.hmod") as pack:
        translation = json.loads(pack.read("assets/create/lang/en_us.json"))
    expected = defaultdict(list)
    for row in fixture["readouts"]:
        key = (row["case"], row["gauge"])
        if row["line"] != len(expected[key]):
            raise RuntimeError(f"Out-of-order Java fixture line for {key}")
        styles = component_styles(row["component"], translation)
        if len(styles) != len(row["text"]):
            raise RuntimeError(f"Wrong style length for Java line {row['text']!r}")
        expected[key].append(tuple(zip(row["text"], styles, strict=True)))
    return expected


def test_draw(args, cases):
    with fixture_world(args, "Goggles-gauges", render=True, pack=args.pack,
                       env={"CREATE_GOGGLES_TRACE": "1"}) as control:
        control.commands((
            "/fill 4 96 -12 10 96 -5 minecraft:smooth_stone",
            "/tp @s 7.5 97 -6.5",
            "/item replace entity @s armor.head with create:goggles",
            "/setblock 6 98 -10 create:speedometer[facing=south]",
            "/setblock 8 98 -10 create:stressometer[facing=south]",
        ))
        for rpm, capacity, stress in cases:
            for x, y, z in GAUGES.values():
                tag = f"{{Speed:{rpm}f,Network:{{Capacity:{capacity}f,Stress:{stress}f}}}}"
                control.command(f"/data merge block {x} {y} {z} {tag}")
                control.call("look-at", x + 0.5, y + 0.5, z + 0.5)
                control.call("wait", 8)
        control.commands((
            "/setblock 10 98 -10 create:chute[facing=down]",
            "/setblock 11 98 -8 create:fluid_tank",
            '/data merge block 11 98 -8 {TankContent:{Fluid:{id:"minecraft:water",amount:2500}}}',
        ))
        control.call("look-at", 10.5, 98.5, -9.5)
        control.call("wait", 8)
        control.call("look-at", 11.5, 98.5, -7.5)
        control.call("wait", 8)


def render_samples(lines):
    for line in lines:
        if not line.startswith("CREATE_GOGGLES "):
            continue
        tick, data = line.removeprefix("CREATE_GOGGLES ").split(" ", 1)
        segments = json.loads(data)
        yield int(tick), [
            tuple((char, (color, strike)) for text, color, strike in row for char in text)
            for row in segments
        ]


def check(fixture):
    expected = expected_readouts(fixture)
    logfile = ROOT / ".local/horizon-goggles-gauges.log"
    observed = [sample for _, sample in render_samples(logfile.read_text().splitlines())]
    if not observed:
        raise RuntimeError("Horizon did not draw a Goggles readout")
    observed_text = ["".join(char for char, _ in row) for sample in observed for row in sample]
    for target_line in (
        "Chute Information", "No attached fans", "Items move Downward",
        "Fluid Container Info:", "Water", "2500 mB / 8000 mB",
    ):
        if not any(target_line in line for line in observed_text):
            raise RuntimeError(f"Missing scoped processing/fluid Goggles readout: {target_line!r}")
    samples = iter(observed)
    for key, wanted in expected.items():
        for sample in samples:
            if sample == wanted:
                break
        else:
            rendered = {tuple("".join(c for c, _ in row) for row in sample) for sample in observed}
            raise RuntimeError(f"Missing Java readout {key}. Horizon drew {sorted(rendered)!r}")
    print(f"Matched all {len(expected)} original Java gauge readouts including text, colors and strikethrough.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    fixture = json.loads((ROOT / "fixtures/goggles-gauge-java.json").read_text())
    test_draw(parser.parse_args(), fixture["cases"])
    check(fixture)


if __name__ == "__main__":
    main()
