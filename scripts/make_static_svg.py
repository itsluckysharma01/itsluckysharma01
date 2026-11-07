#!/usr/bin/env python3
"""Build a motion-free copy of an animated SVG.

Removes every SMIL element (<animate>, <animateTransform>, <animateMotion>,
<set>) and parks orbiting nodes at a fixed point on their orbit, so the static
file looks like a finished frame rather than a paused one.

    python3 scripts/make_static_svg.py assets/lucky-hero.svg assets/lucky-hero-static.svg
"""
import re
import sys

# Where to park elements that move along a <mpath>, keyed by the path id.
PARKED = {
    "lsh-hero-orbit-a": (200, -49),
    "lsh-hero-orbit-b": (132, -87),
}

MOTION = re.compile(
    r'(<circle\b[^>]*?)>\s*<animateMotion\b[^>]*>\s*<mpath href="#([\w-]+)"\s*/>\s*</animateMotion>\s*</circle>',
    re.S,
)


def park(match):
    head, ref = match.group(1), match.group(2)
    x, y = PARKED.get(ref, (0, 0))
    return f'{head} transform="translate({x} {y})"/>'


def main(src, dst):
    svg = open(src, encoding="utf-8").read()
    svg = MOTION.sub(park, svg)
    svg = re.sub(r"<(animate|animateTransform|animateMotion|set)\b[^>]*/>", "", svg)
    svg = re.sub(r"<(animate|animateTransform|animateMotion)\b[^>]*>.*?</\1>", "", svg, flags=re.S)
    svg = svg.replace("</desc>", " Static version without motion.</desc>", 1)
    svg = re.sub(r"\n\s*\n", "\n", svg)
    open(dst, "w", encoding="utf-8").write(svg)


if __name__ == "__main__":
    main(*sys.argv[1:3])
