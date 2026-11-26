"""Slide 6 trade-off chart: test-set accuracy vs median latency, one point per speed-tested configuration.

Reads only the analysis outputs, so every coordinate traces to a file already shown on Slides 4 and 5:
  y  analysis/output/accuracy_a2/pass_fail_a2.csv, cascade_pass_fail_a2.csv  (correct / 101)
  x  analysis/output/speed_a2/per_config.csv  (p50_mean_ms over the runs the frozen rule counts;
     p50_per_run_ms for the runs flagged queued, drawn faint and not counted)
  limit line  qwen2.5:7b's test accuracy minus 10 percentage points (docs/a2/accuracy_limits.md section 1)

Standard library only. Writes slide6_tradeoff.svg and slide6_tradeoff_points.csv next to this file.
Run from the repository root: python slides/drafts_a2/slide6_tradeoff_chart.py
"""

import csv
import re
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
ACC = ROOT / "analysis/output/accuracy_a2"
SPEED = ROOT / "analysis/output/speed_a2/per_config.csv"
REFERENCE = "qwen2.5:7b"

# Categorical slots 1-3 of the reference palette, validated all-pairs on the light surface.
COLORS = {"qwen2.5:7b": "#2a78d6", "cascade-A": "#eb6834", "cascade-B": "#1baf7a"}
NAMES = {"qwen2.5:7b": "qwen2.5:7b alone", "cascade-A": "Cascade, Setting A", "cascade-B": "Cascade, Setting B"}
SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984", "#e6e5e1"


def read(path):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def points():
    accuracy = {r["model_tag"]: r for r in read(ACC / "pass_fail_a2.csv") + read(ACC / "cascade_pass_fail_a2.csv")}
    rows = []
    for r in read(SPEED):
        config = r["config"]
        acc = accuracy[config]  # every speed-tested configuration must have been scored
        runs = re.findall(r"(run\d+)=([\d.]+)( \[queued\])?", r["p50_per_run_ms"])
        rows.append(dict(
            config=config, label=NAMES.get(config, config), correct=int(acc["correct"]),
            test_n=int(acc["test_set_n"]), accuracy_pct=int(acc["correct"]) / int(acc["test_set_n"]) * 100,
            qualifies=acc["qualifies"] == "True", runs_counted=r["runs_counted"],
            p50_s=float(r["p50_mean_ms"]) / 1000,
            queued_runs_s="; ".join(f"{n}={float(v) / 1000:.2f}" for n, v, q in runs if q)))
    ref = accuracy[REFERENCE]
    limit = (Fraction(int(ref["correct"]), int(ref["test_set_n"])) - Fraction(1, 10)) * 100
    return rows, float(limit)


def svg(rows, limit):
    W, H, L, R, T, B = 960, 540, 84, 36, 28, 118
    x0, x1, y0, y1 = 0.0, 11.0, 60.0, 80.0
    sx = lambda v: L + (v - x0) / (x1 - x0) * (W - L - R)
    sy = lambda v: T + (y1 - v) / (y1 - y0) * (H - T - B)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
           f'font-family="Segoe UI, Helvetica, Arial, sans-serif">',
           '<title>Test-set accuracy vs median latency, one point per speed-tested configuration</title>',
           f'<rect width="{W}" height="{H}" fill="{SURFACE}"/>']
    for v in range(int(y0), int(y1) + 1, 5):  # recessive grid and axis labels
        out.append(f'<line x1="{L}" x2="{W - R}" y1="{sy(v):.1f}" y2="{sy(v):.1f}" stroke="{GRID}" stroke-width="1"/>')
        out.append(f'<text x="{L - 10}" y="{sy(v) + 4:.1f}" font-size="13" fill="{INK2}" text-anchor="end">{v}%</text>')
    for v in range(int(x0), int(x1) + 1, 2):
        out.append(f'<text x="{sx(v):.1f}" y="{H - B + 22}" font-size="13" fill="{INK2}" text-anchor="middle">{v} s</text>')
    out.append(f'<line x1="{L}" x2="{W - R}" y1="{H - B}" y2="{H - B}" stroke="{MUTED}" stroke-width="1"/>')
    out.append(f'<text x="{(L + W - R) / 2}" y="{H - B + 46}" font-size="14" fill="{INK}" text-anchor="middle">'
               'Median latency under load (p50 of the counted run, seconds)</text>')
    out.append(f'<text transform="translate(22 {(T + H - B) / 2}) rotate(-90)" font-size="14" fill="{INK}" '
               'text-anchor="middle">Overall accuracy, 101 test tickets</text>')
    ly = sy(limit)  # overall limit line
    out.append(f'<line x1="{L}" x2="{W - R}" y1="{ly:.1f}" y2="{ly:.1f}" stroke="{INK2}" stroke-width="2" stroke-dasharray="6 5"/>')
    out.append(f'<text x="{W - R - 4}" y="{ly + 18:.1f}" font-size="13" fill="{INK2}" text-anchor="end">'
               f'Overall limit {limit:.2f}% (pass needs at least 65/101)</text>')
    # Faint hollow markers: runs the frozen no-queue rule flagged, listed but not counted.
    for p in rows:
        for item in filter(None, p["queued_runs_s"].split("; ")):
            v = float(item.split("=")[1])
            out.append(f'<circle cx="{sx(v):.1f}" cy="{sy(p["accuracy_pct"]):.1f}" r="5" fill="none" '
                       f'stroke="{COLORS.get(p["config"], INK2)}" stroke-width="1.5" opacity="0.55"/>')
    # Counted points: filled if the configuration passes both accuracy limits, hollow if it fails.
    offsets = {"qwen2.5:7b": (-14, -16, "end"), "cascade-A": (0, -18, "middle"), "cascade-B": (14, 26, "start")}
    for p in rows:
        c = COLORS.get(p["config"], INK2)
        cx, cy = sx(p["p50_s"]), sy(p["accuracy_pct"])
        fill = c if p["qualifies"] else SURFACE
        out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="8" fill="{fill}" stroke="{SURFACE}" stroke-width="2"/>')
        if not p["qualifies"]:
            out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="7" fill="none" stroke="{c}" stroke-width="2"/>')
        dx, dy, anchor = offsets.get(p["config"], (12, -14, "start"))
        status = "" if p["qualifies"] else " · fails accuracy"
        out.append(f'<text x="{cx + dx:.1f}" y="{cy + dy:.1f}" font-size="14" fill="{INK}" text-anchor="{anchor}">'
                   f'<tspan font-weight="600">{p["label"]}</tspan>'
                   f'<tspan fill="{INK2}"> {p["correct"]}/{p["test_n"]} · {p["p50_s"]:.2f} s{status}</tspan></text>')
    ky = H - 26  # legend, one row
    out.append(f'<circle cx="{L + 8}" cy="{ky - 4}" r="7" fill="{INK2}"/>')
    out.append(f'<text x="{L + 22}" y="{ky}" font-size="13" fill="{INK2}">Counted run (frozen no-queue rule)</text>')
    out.append(f'<circle cx="{L + 278}" cy="{ky - 4}" r="5" fill="none" stroke="{INK2}" stroke-width="1.5" opacity="0.55"/>')
    out.append(f'<text x="{L + 292}" y="{ky}" font-size="13" fill="{INK2}">Run flagged queued, not counted</text>')
    out.append(f'<line x1="{L + 528}" x2="{L + 556}" y1="{ky - 4}" y2="{ky - 4}" stroke="{INK2}" stroke-width="2" stroke-dasharray="6 5"/>')
    out.append(f'<text x="{L + 564}" y="{ky}" font-size="13" fill="{INK2}">Overall accuracy limit</text>')
    out.append("</svg>")
    return "\n".join(out)


def main():
    rows, limit = points()
    (HERE / "slide6_tradeoff.svg").write_text(svg(rows, limit), encoding="utf-8")
    with (HERE / "slide6_tradeoff_points.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    for p in rows:
        print(f"{p['label']}: {p['correct']}/{p['test_n']} ({p['accuracy_pct']:.2f}%), "
              f"p50 {p['p50_s']:.2f} s [{p['runs_counted']}], qualifies={p['qualifies']}")
    print(f"overall limit {limit:.2f}%")


if __name__ == "__main__":
    main()
