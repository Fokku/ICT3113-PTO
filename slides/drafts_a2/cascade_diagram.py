#!/usr/bin/env python3
"""Draw the Slide 2 cascade diagram: small model -> escalation rule -> (large model).

Owner: Part 1 -- Yeo Kai Yuan (Slide 2 diagram; TODO_A2.md §1.6).

The diagram is drawn from the code, not from memory: the two settings' wording
comes from ``service/cascade.py`` ``RULE_SETTINGS`` (each rule's ``describe()``,
the literal condition), so the slide cannot show a rule the service does not
run. Until Part 2's settings are copied in, the settings line says so instead.
The model pair comes from the command line (the pair the memory check
confirmed, docs/environment/a2-memory-check/).

Usage:
    python slides/drafts_a2/cascade_diagram.py --small llama3.2:3b --large qwen2.5:7b
Writes slides/drafts_a2/cascade_diagram.png (and .svg) at 16:9-friendly size.
"""

from __future__ import annotations

import argparse
import sys
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon  # noqa: E402

from service import cascade  # noqa: E402

# The A1 deck's palette (slides/build_deck.js), so the image sits in the deck.
INK, MUTED, LINE = "#17252C", "#5B6B73", "#C9D5D8"
TEAL, TEAL_LIGHT = "#1F6F78", "#D5E8EA"
AMBER, AMBER_LIGHT = "#E39B2D", "#FBEBD2"
PASS, LIGHT = "#2E7D5B", "#EEF3F4"


def box(ax, x, y, w, h, title, body, face, edge):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                facecolor=face, edgecolor=edge, linewidth=1.6))
    ax.text(x + w / 2, y + h * 0.66, title, ha="center", va="center", fontsize=12.5,
            fontweight="bold", color=INK, family="DejaVu Sans")
    ax.text(x + w / 2, y + h * 0.30, body, ha="center", va="center", fontsize=9.5,
            color=MUTED, family="DejaVu Sans", linespacing=1.3)


def arrow(ax, start, end, label="", color=INK, dashed=False, label_xy=None):
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=16, linewidth=1.6,
                                 color=color, linestyle=(0, (4, 3)) if dashed else "-"))
    if label:
        lx, ly = label_xy or ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2 + 0.12)
        ax.text(lx, ly, label, ha="center", va="bottom", fontsize=10, color=color,
                fontweight="bold", family="DejaVu Sans")


def setting_lines() -> tuple[list[str], bool]:
    lines, length_rule = [], False
    for setting in ("A", "B"):
        rule = cascade.RULE_SETTINGS.get(setting)
        if rule is None:
            lines.append(f"Setting {setting}: not yet written into service/cascade.py "
                         f"(copy from cascade/escalation_rule.md §3)")
        else:
            lines.append(f"Setting {setting}: {rule.describe()}")
            length_rule = length_rule or isinstance(rule, cascade.LengthRule)
    return lines, length_rule


def draw(small: str, large: str, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(12, 5.2), dpi=200)
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 5.2)
    ax.axis("off")

    # Lane 1: request -> small model -> rule -> return
    box(ax, 0.2, 2.9, 2.2, 1.2, "POST /tickets", "one ticket in,\none category out", LIGHT, LINE)
    box(ax, 2.75, 2.9, 2.75, 1.2, "Small model", f"{small}\nunchanged prompt", TEAL_LIGHT, TEAL)
    diamond = Polygon([[6.75, 4.25], [7.85, 3.5], [6.75, 2.75], [5.65, 3.5]], closed=True,
                      facecolor=AMBER_LIGHT, edgecolor=AMBER, linewidth=1.6)
    ax.add_patch(diamond)
    ax.text(6.75, 3.58, "Escalation\nrule", ha="center", va="center", fontsize=11, fontweight="bold",
            color=INK, family="DejaVu Sans")
    ax.text(6.75, 3.08, "A or B", ha="center", va="center", fontsize=9, color=MUTED, family="DejaVu Sans")
    box(ax, 9.4, 2.9, 2.4, 1.2, "Return category", "same response shape\nwhichever model answered",
        LIGHT, LINE)

    # Lane 2: large model
    box(ax, 5.4, 0.75, 2.7, 1.2, "Large model", f"{large}\nsame unchanged prompt", TEAL_LIGHT, TEAL)

    arrow(ax, (2.4, 3.5), (2.75, 3.5))
    arrow(ax, (5.5, 3.5), (5.65, 3.5))
    arrow(ax, (7.85, 3.5), (9.4, 3.5), "accept", color=PASS)
    arrow(ax, (6.75, 2.75), (6.75, 1.95), "escalate", color=AMBER, label_xy=(7.35, 2.2))
    arrow(ax, (8.1, 1.35), (10.6, 2.9), color=INK)

    lines, length_rule = setting_lines()
    if length_rule:
        arrow(ax, (1.3, 2.9), (5.4, 1.35), "long ticket: skips the small model", color=MUTED,
              dashed=True, label_xy=(2.6, 1.85))

    ax.text(0.2, 0.42, "\n".join(textwrap.shorten(l, 150, placeholder=" ...") for l in lines),
            ha="left", va="center", fontsize=9, color=INK, family="DejaVu Sans", linespacing=1.4)
    ax.text(0.2, 4.85, "Both models stay resident together (memory check: `ollama ps` lists both).  "
            "The service log records, per ticket, which model answered and whether it escalated.",
            ha="left", va="center", fontsize=9.5, color=MUTED, family="DejaVu Sans")

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    fig.savefig(out.with_suffix(".svg"), bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--small", default="<small model>", help="the cascade's small model tag")
    parser.add_argument("--large", default="qwen2.5:7b")
    parser.add_argument("--out", type=Path, default=Path(__file__).with_name("cascade_diagram.png"))
    args = parser.parse_args(argv)
    draw(args.small, args.large, args.out)
    print(f"wrote {args.out} and {args.out.with_suffix('.svg')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
