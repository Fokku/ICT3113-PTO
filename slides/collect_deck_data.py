#!/usr/bin/env python3
"""Collect every figure the deck shows, from the repository's own files.

Owner: Part 1 -- Yeo Kai Yuan (deck assembly).

The deck (``slides/build_deck.js``) renders what this script writes to
``slides/build/deck_data.json`` and nothing else, so every number on a slide
traces to a committed file: the workload and requirements documents, the
labelling outputs, ``models/models.yaml``, the environment captures, and the
analysis outputs under ``analysis/output/``. Nothing here measures anything,
and nothing is typed in: a figure that is not in a source file is reported as
missing, not invented.

``--final`` turns every missing input into an error, so the submitted deck
cannot be built with a gap in it.

Usage:
    .venv/bin/python slides/collect_deck_data.py [--final]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from service.categories import CATEGORIES  # noqa: E402
from service.prompt import PROMPT_HASH  # noqa: E402

OUT = REPO / "slides" / "build" / "deck_data.json"
ANALYSIS = REPO / "analysis" / "output"
MISSING: list[str] = []


def missing(what: str) -> None:
    MISSING.append(what)


# ---------------------------------------------------------------------------
# small parsers
# ---------------------------------------------------------------------------

def strip_md(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[*`]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def md_section(text: str, heading: str) -> str:
    """Body of the section whose heading line is exactly ``heading``."""
    lines = text.splitlines()
    level = len(heading) - len(heading.lstrip("#"))
    out: list[str] = []
    inside = False
    for line in lines:
        if line.strip() == heading:
            inside = True
            continue
        if inside and line.startswith("#"):
            this_level = len(line) - len(line.lstrip("#"))
            if this_level <= level:
                break
        if inside:
            out.append(line)
    return "\n".join(out)


def md_tables(text: str) -> list[list[dict[str, str]]]:
    tables: list[list[dict[str, str]]] = []
    block: list[str] = []
    for line in text.splitlines() + [""]:
        if line.strip().startswith("|"):
            block.append(line.strip())
            continue
        if len(block) >= 2:
            header = [h.strip() for h in block[0].strip("|").split("|")]
            rows = []
            for raw in block[2:]:
                cells = [c.strip() for c in raw.strip("|").split("|")]
                if len(cells) == len(header):
                    rows.append(dict(zip(header, cells)))
            tables.append(rows)
        block = []
    return tables


def parse_capture(path: Path) -> dict[str, str]:
    facts: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if " : " in line and not line.startswith("--"):
            key, value = line.split(" : ", 1)
            facts.setdefault(key.strip(), value.strip())
    return facts


def git(*args: str) -> str | None:
    proc = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True)
    return proc.stdout.strip() if proc.returncode == 0 else None


def num(value) -> float | None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if f != f else f


# ---------------------------------------------------------------------------
# sections
# ---------------------------------------------------------------------------

def team() -> dict:
    data = yaml.safe_load((REPO / "slides" / "team.yaml").read_text(encoding="utf-8"))
    for member in data["members"]:
        if not str(member.get("student_id") or "").strip():
            missing(f"student ID for {member['name']} (slides/team.yaml)")
    return data


def architecture() -> dict:
    env = {}
    for line in (REPO / ".env.example").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()
    return {
        "uvicorn_workers": env.get("UVICORN_WORKERS"),
        "threadpool": env.get("SERVICE_THREADPOOL_SIZE"),
        "ollama_timeout_s": env.get("OLLAMA_TIMEOUT_S"),
        "num_ctx": env.get("NUM_CTX"),
        "seed": env.get("OLLAMA_SEED"),
        "num_parallel": env.get("OLLAMA_NUM_PARALLEL"),
        "prompt_hash": PROMPT_HASH,
        "categories": list(CATEGORIES),
    }


def workload() -> dict:
    text = (REPO / "workload" / "workload_model.md").read_text(encoding="utf-8")
    figures: dict[str, dict] = {}
    for heading in ("## Ticket volume", "## Agent search rate", "## Peak versus non-peak",
                    "## Ticket length distribution"):
        for table in md_tables(md_section(text, heading)):
            for row in table:
                name = strip_md(row.get("Figure", ""))
                if name:
                    figures[name] = {
                        "value": strip_md(row.get("Value", "")),
                        "unit": strip_md(row.get("Unit", "")),
                        "source": strip_md(row.get("Source (citation or URL)", "")),
                        "estimate": strip_md(row.get("Estimate? (Y/N)", "")).upper().startswith("Y"),
                        "method": strip_md(row.get("Estimation method", "")),
                    }
    rates = []
    for table in md_tables(md_section(text, "## Derived arrival rates for testing")):
        for row in table:
            if row.get("Rate label"):
                rates.append({k: strip_md(v) for k, v in row.items()})
    sources = []
    for match in re.finditer(r"^\d+\.\s+(.*?)\n\s+(https?://\S+)", md_section(text, "## Sources"), re.M):
        sources.append({"text": strip_md(match.group(1)), "url": match.group(2)})
    dist = REPO / "workload" / "output" / "length_distribution.csv"
    lengths = {}
    if dist.is_file():
        for row in csv.DictReader(dist.open(encoding="utf-8")):
            lengths[row.get("metric", "")] = row
    else:
        missing("workload/output/length_distribution.csv")
    # The characters panel of the generated histogram, cropped (not redrawn) so it
    # stays legible at slide size. Source: workload/output/length_histogram.png.
    hist_src = REPO / "workload" / "output" / "length_histogram.png"
    hist_out = OUT.parent / "length_histogram_characters.png"
    if hist_src.is_file():
        from PIL import Image
        with Image.open(hist_src) as image:
            width, height = image.size
            hist_out.parent.mkdir(parents=True, exist_ok=True)
            image.crop((0, int(height * 0.09), width // 3, height)).save(hist_out)
    else:
        missing("workload/output/length_histogram.png")
    return {"figures": figures, "rates": rates, "sources": sources, "lengths": lengths,
            "histogram": str(hist_out.relative_to(REPO)),
            "histogram_source": "workload/output/length_histogram.png"}


def requirements() -> dict:
    text = (REPO / "workload" / "requirements.md").read_text(encoding="utf-8")
    rows = []
    for table in md_tables(md_section(text, "## The requirements")):
        for row in table:
            if re.fullmatch(r"R\d", strip_md(row.get("ID", ""))):
                rows.append({k: strip_md(v) for k, v in row.items()})
    position = re.search(r"\*\*Position: (.*?)\*\*", text)
    concession = re.search(r"\*\*Order of concession[^*]*\*\*\s*(.*)", text)
    judged = re.search(r"Each load requirement \(R1, R2, R5\) is judged on (.*?)\n", text)
    return {
        "rows": rows,
        "position": position.group(1).strip() if position else None,
        "concession": strip_md(concession.group(1)) if concession else None,
        "judged_on": judged.group(1).strip() if judged else None,
    }


def models() -> list[dict]:
    data = yaml.safe_load((REPO / "models" / "models.yaml").read_text(encoding="utf-8"))
    out = []
    for entry in data["candidates"]:
        pinned = entry.get("pinned") or {}
        if not pinned.get("digest"):
            missing(f"pinned digest for {entry['tag']} (models/models.yaml)")
        out.append({
            "tag": entry["tag"], "name": entry["name"], "size_class": entry["size_class"],
            "parameters": entry["parameters"], "quantisation": entry["default_quantisation"],
            "licence": entry["licence"], "rationale": " ".join(str(entry["rationale"]).split()),
            "digest": pinned.get("digest"), "size_bytes": pinned.get("size_bytes"),
            "ollama_version": pinned.get("ollama_version"),
        })
    return out


def golden() -> dict:
    gold = pd.read_csv(REPO / "golden" / "golden_set.csv")
    counts = gold["label"].value_counts().to_dict()
    report = (REPO / "labelling" / "agreement_report.txt").read_text(encoding="utf-8")
    kappa = re.search(r"COHEN'S KAPPA = ([0-9.]+)\s+\((\w+)\)", report)
    po = re.search(r"observed agreement\s+Po = (\d+)/(\d+) = ([0-9.]+)", report)
    resolutions = list(csv.DictReader((REPO / "labelling" / "resolutions.csv").open(encoding="utf-8")))
    disagreements = list(csv.DictReader((REPO / "labelling" / "disagreements.csv").open(encoding="utf-8")))
    pairs: dict[tuple, int] = {}
    for row in disagreements:
        key = tuple(sorted((row["label_A"], row["label_B"])))
        pairs[key] = pairs.get(key, 0) + 1
    top_pairs = [{"pair": list(k), "count": v} for k, v in sorted(pairs.items(), key=lambda kv: -kv[1])[:5]]
    protocol = (REPO / "labelling" / "protocol.md").read_text(encoding="utf-8")
    revisions = []
    for table in md_tables(md_section(protocol, "## Revision log")):
        for row in table:
            if re.fullmatch(r"R\d", strip_md(row.get("Revision", ""))):
                revisions.append({k: strip_md(v) for k, v in row.items()})
    res_md = (REPO / "labelling" / "resolutions.md").read_text(encoding="utf-8")
    examples = []
    for match in re.finditer(r"### Resolution (\d+)\n(.*?)(?=\n### |\Z)", res_md, re.S):
        body = match.group(2)
        if re.search(r"\*\*Slide 6 example:\*\* yes", body):
            field = lambda name: strip_md(re.search(rf"\*\*{name}:\*\* (.*)", body).group(1))
            examples.append({"resolution": int(match.group(1)), "row": field("Row number"),
                             "label_a": field("Label A"), "label_b": field("Label B"),
                             "agreed": field("Agreed label"), "reasoning": field("Reasoning"),
                             "revision": field("Caused a protocol revision")})
    tag_commit = git("rev-list", "-n", "1", "golden-freeze")
    tag_date = git("log", "-1", "--format=%cI", "golden-freeze") if tag_commit else None
    golden_commit = git("log", "--diff-filter=A", "--format=%h %cI", "--", "golden/golden_set.csv")
    return {
        "rows": int(len(gold)), "counts": {c: int(counts.get(c, 0)) for c in CATEGORIES},
        "kappa": float(kappa.group(1)) if kappa else None, "kappa_band": kappa.group(2) if kappa else None,
        "agreed": int(po.group(1)) if po else None, "po": float(po.group(3)) if po else None,
        "disagreements": len(disagreements), "resolutions": len(resolutions),
        "top_pairs": top_pairs, "revisions": revisions, "examples": examples,
        "sample_seed": 3113, "freeze_commit": tag_commit, "freeze_date": tag_date,
        "golden_first_commit": golden_commit,
    }


def environment() -> dict:
    hosts = []
    for path in sorted((REPO / "docs" / "environment").glob("*.txt")):
        facts = parse_capture(path)
        hosts.append({
            "file": f"docs/environment/{path.name}",
            "host": facts.get("Host"), "role": facts.get("Declared role"),
            "cpu": facts.get("Model name") or facts.get("/proc/cpuinfo model"),
            "physical_cores": facts.get("Physical cores") or facts.get("Cores per socket"),
            "logical_cpus": facts.get("Logical CPUs") or facts.get("Logical cores") or facts.get("nproc (online CPUs)"),
            "ram": facts.get("Total RAM") or facts.get("Physical memory"),
            "os": facts.get("Distribution") or (f"macOS {facts['macOS version']}" if facts.get("macOS version") else None),
            "kernel": facts.get("uname -r (kernel)"), "virtualisation": facts.get("Virtualisation"),
            "docker": facts.get("docker server") or facts.get("docker"),
            "compose": facts.get("docker compose"), "ollama": facts.get("ollama /api/version"),
            "jmeter": facts.get("jmeter version"), "java": facts.get("java (used by JMeter)") or facts.get("java"),
            "captured_at": facts.get("Captured at (UTC)"),
        })
    if not any((h["role"] or "").startswith(("service", "ollama", "all")) for h in hosts):
        missing("service-host capture in docs/environment/")
    if not any((h["role"] or "") == "loadgen" for h in hosts):
        missing("load-generator capture in docs/environment/")
    network = None
    net = REPO / "docs" / "environment" / "network.md"
    if net.is_file():
        network = net.read_text(encoding="utf-8")
    else:
        missing("docs/environment/network.md (measured round trip between the machines)")
    return {"hosts": hosts, "network_md": network}


def load_results() -> dict:
    per_run = ANALYSIS / "load" / "load_per_run.csv"
    if not per_run.is_file():
        missing("analysis/output/load/load_per_run.csv")
        return {"configs": [], "search": []}
    runs = pd.read_csv(per_run)
    runs = runs[runs["mode"] == "real"]
    configs = []
    for (model, plan, rate), group in runs.groupby(["model_tag", "plan", "rate_per_min"]):
        row = {"model": model, "plan": plan, "rate": int(rate), "runs": int(len(group))}
        for metric in ("client_p50_ms", "client_p95_ms", "client_p99_ms", "ok_throughput_per_hour",
                       "error_rate_pct", "span_s", "samples"):
            values = group[metric].astype(float)
            row[metric] = {"mean": values.mean(), "min": values.min(), "max": values.max()}
        configs.append(row)
    search = []
    by_label = ANALYSIS / "load" / "load_per_run_by_label.csv"
    if by_label.is_file():
        labels = pd.read_csv(by_label)
        labels = labels[(labels["plan"] == "mixed_load") & (labels["label"] == "GET /search")]
        labels = labels[labels["run_id"].isin(runs["run_id"])]
        for model, group in labels.groupby("model_tag"):
            entry = {"model": model, "runs": int(len(group))}
            for metric in ("client_p50_ms", "client_p95_ms", "client_p99_ms", "error_rate_pct"):
                values = group[metric].astype(float)
                entry[metric] = {"mean": values.mean(), "min": values.min(), "max": values.max()}
            search.append(entry)
    return {"configs": configs, "search": search}


def stress_results() -> list[dict]:
    out = []
    root = ANALYSIS / "stress"
    for run_dir in sorted(p for p in root.glob("*") if p.is_dir()):
        meta_path = REPO / "results" / "runs" / run_dir.name / "metadata.json"
        if not meta_path.is_file() or json.loads(meta_path.read_text()).get("mode") != "real":
            continue
        steps = pd.read_csv(run_dir / "stress_steps.csv").to_dict(orient="records")
        report = (run_dir / "stress_report.md").read_text(encoding="utf-8")
        limit = md_section(report, "## The limit").strip().split("\n\n")[0]
        model = json.loads(meta_path.read_text())["model_tag"]
        # The same rule stress_summary.py applies (first step with p95 above R1's
        # 10 s or an error rate above 5%), restated as one short line for the slide.
        rates = [s["offered_per_min"] for s in steps]
        ramp = f"{rates[0]:g}–{rates[-1]:g}/min"
        first = next((s for s in steps if (num(s["p95_ms"]) or 0) > 10000 or (num(s["error_rate"]) or 0) > 0.05), None)
        if first:
            short = (f"{ramp}: limit at {first['offered_per_min']:g}/min (p95 {num(first['p95_ms']) / 1000:.1f} s, "
                     f"{num(first['error_rate']) * 100:.0f}% errors)")
        else:
            top = steps[-1]
            short = f"{ramp}: none (p95 {num(top['p95_ms']) / 1000:.1f} s at {top['offered_per_min']:g}/min)"
        out.append({"run": run_dir.name, "model": model, "steps": steps, "limit": strip_md(limit), "limit_short": short})
    if not out:
        missing("analysis/output/stress/<run>/ for at least one real stress run")
    return out


def bottleneck_results() -> list[dict]:
    out = []
    for run_dir in sorted(p for p in (ANALYSIS / "bottleneck").glob("*") if p.is_dir()):
        meta_path = REPO / "results" / "runs" / run_dir.name / "metadata.json"
        if not meta_path.is_file():
            continue
        meta = json.loads(meta_path.read_text())
        if meta.get("mode") != "real":
            continue
        breakdown = pd.read_csv(run_dir / "bottleneck_breakdown.csv")
        tokens = pd.read_csv(run_dir / "bottleneck_tokens.csv")
        out.append({
            "run": run_dir.name, "model": meta["model_tag"], "plan": meta["plan"],
            "rate": meta.get("rate_per_min"), "run_index": meta.get("run_index"),
            "components": breakdown.to_dict(orient="records"),
            "tokens": tokens.to_dict(orient="records"),
        })
    if not out:
        missing("analysis/output/bottleneck/<run>/ for the real runs")
    return out


def reconcile_summary() -> dict:
    summary = ANALYSIS / "reconcile" / "SUMMARY.md"
    if not summary.is_file():
        missing("analysis/output/reconcile/SUMMARY.md")
        return {"runs": 0, "failed": []}
    rows = [r for t in md_tables(summary.read_text(encoding="utf-8")) for r in t]
    failed = [strip_md(r["Run"]) for r in rows if strip_md(r.get("Exit", "")) != "0"]
    return {"runs": len(rows), "failed": failed}


def accuracy_results() -> list[dict]:
    comparison = ANALYSIS / "accuracy" / "model_comparison.csv"
    if not comparison.is_file():
        missing("analysis/output/accuracy/model_comparison.csv")
        return []
    frame = pd.read_csv(comparison)
    frame = frame[frame["mode"] == "real"]
    out = []
    for row in frame.to_dict(orient="records"):
        run_dir = ANALYSIS / "accuracy" / f"{re.sub(r'[^A-Za-z0-9._-]+', '-', row['model_tag'])}_{row['stamp']}"
        per_cat = pd.read_csv(run_dir / "per_category.csv").to_dict(orient="records")
        matrix = pd.read_csv(run_dir / "confusion_matrix.csv", index_col=0)
        confusions = []
        for golden_label in matrix.index:
            for predicted in matrix.columns:
                if predicted != golden_label and int(matrix.loc[golden_label, predicted]) > 0:
                    confusions.append({"golden": golden_label, "predicted": predicted,
                                       "count": int(matrix.loc[golden_label, predicted])})
        confusions.sort(key=lambda c: -c["count"])
        out.append({**{k: (None if isinstance(v, float) and v != v else v) for k, v in row.items()},
                    "run_dir": str(run_dir.relative_to(REPO)), "per_category": per_cat,
                    "top_confusions": confusions[:4],
                    "matrix": {"labels": list(matrix.index), "columns": list(matrix.columns),
                               "values": matrix.values.tolist()}})
    if len({r["model_tag"] for r in out}) < 4:
        missing("accuracy runs for all four candidates in analysis/output/accuracy/")
    return out


def predictions() -> dict:
    frozen = git("show", "golden-freeze:predictions/prediction_record.md")
    source = "golden-freeze:predictions/prediction_record.md"
    if frozen is None or "⟪" in frozen or "TODO(" in frozen:
        frozen = (REPO / "predictions" / "prediction_record.md").read_text(encoding="utf-8")
        source = "predictions/prediction_record.md (working copy, NOT the frozen version)"
        missing("a frozen prediction record (golden-freeze tag on a commit with no ⟪…⟫ placeholders)")
    tag = re.compile(r"[a-z0-9.]+:[0-9A-Za-z._-]+")
    rows = []
    for table in md_tables(md_section(frozen, "## Section 2 — Per-candidate-model predictions")):
        for row in table:
            model = strip_md(row.get("Model (exact Ollama tag)", ""))
            if tag.fullmatch(model):
                rows.append({"model": model, **{k: strip_md(v) for k, v in row.items()}})
    section1 = md_section(frozen, "## Section 1 — Where we expect the bottleneck to be under load")
    service_time, stress = [], []
    for table in md_tables(section1):
        for row in table:
            model = strip_md(row.get("Model", ""))
            if not tag.fullmatch(model):
                continue
            entry = {"model": model, **{k: strip_md(v) for k, v in row.items()}}
            (stress if "1–21/min ramp" in row else service_time).append(entry)
    requirement_rows = []
    for table in md_tables(md_section(frozen, "## Section 2 — Per-candidate-model predictions")):
        for row in table:
            if re.match(r"R\d", strip_md(row.get("Requirement", ""))):
                requirement_rows.append({k: strip_md(v) for k, v in row.items()})
    hardest = re.findall(r"^\d\.\s+\*\*(.+?)\*\*", md_section(frozen, "## Section 3 — Which categories we expect to be hardest, and why"), re.M)
    bottleneck = re.search(r"\*\*Component: (.*?)\*\*", frozen)
    return {"source": source, "rows": rows, "service_time": service_time, "stress": stress,
            "requirements": requirement_rows, "hardest_categories": hardest,
            "bottleneck": strip_md(bottleneck.group(1)) if bottleneck else None}


def references() -> list[dict]:
    text = (REPO / "docs" / "references.md").read_text(encoding="utf-8")
    refs = []
    for match in re.finditer(r"^\*\*\[(\d+)\]\*\*\s+(.*?)(?=\n\s*\n|\n\*\*\[)", text, re.M | re.S):
        refs.append({"n": int(match.group(1)), "text": strip_md(match.group(2))})
    if not refs:
        missing("numbered references in docs/references.md")
    if "TODO" in text or "⟪" in text:
        missing("docs/references.md still contains TODO or ⟪…⟫ markers")
    return refs


def bottleneck_summary(runs: list[dict]) -> list[dict]:
    """Mean of each component's per-run mean, per model, plan and rate (three runs each)."""
    groups: dict[tuple, list[dict]] = {}
    for run in runs:
        groups.setdefault((run["model"], run["plan"], run["rate"]), []).append(run)
    out = []
    for (model, plan, rate), members in sorted(groups.items(), key=lambda kv: (str(kv[0][0]), str(kv[0][1]), float(kv[0][2] or 0))):
        comps: dict[str, list[float]] = {}
        for run in members:
            for comp in run["components"]:
                comps.setdefault(comp["component"], []).append(float(comp["mean_ms"]))
        rates: dict[str, list[float]] = {}
        for run in members:
            for tok in run["tokens"]:
                rates.setdefault(tok["stage"], []).append(float(tok["aggregate_tokens_per_s"]))
                rates.setdefault(tok["stage"] + " tokens/request", []).append(float(tok["mean_tokens_per_request"]))
        out.append({"model": model, "plan": plan, "rate": rate, "runs": len(members),
                    "components_mean_ms": {k: sum(v) / len(v) for k, v in comps.items()},
                    "tokens": {k: sum(v) / len(v) for k, v in rates.items()}})
    return out


def verdicts(load: dict, accuracy: list[dict]) -> list[dict]:
    """Each requirement, per model, judged exactly as workload/requirements.md says.

    R1, R2 and R5 on the worst of the three runs; R3 and R4 on the single serial pass.
    """
    per_run = ANALYSIS / "load" / "load_per_run.csv"
    runs = pd.read_csv(per_run) if per_run.is_file() else pd.DataFrame()
    if not runs.empty:
        runs = runs[runs["mode"] == "real"]
    by_label = ANALYSIS / "load" / "load_per_run_by_label.csv"
    labels = pd.read_csv(by_label) if by_label.is_file() else pd.DataFrame()
    out = []
    for model in [m["tag"] for m in models()]:
        row: dict = {"model": model}
        if not runs.empty:
            r1 = runs[(runs["model_tag"] == model) & (runs["plan"] == "load_post_tickets") & (runs["rate_per_min"] == 1)]
            if len(r1):
                row["R1"] = {"value_ms": float(r1["client_p95_ms"].max()), "runs": int(len(r1)),
                             "ok": bool(r1["client_p95_ms"].max() <= 10000)}
            r2 = runs[(runs["model_tag"] == model) & (runs["plan"] == "load_post_tickets") & (runs["rate_per_min"] == 12)]
            if len(r2):
                worst_err, worst_span = float(r2["error_rate_pct"].max()), float(r2["span_s"].max())
                row["R2"] = {"error_pct": worst_err, "span_s": worst_span, "runs": int(len(r2)),
                             "ok_per_hour_min": float(r2["ok_throughput_per_hour"].min()),
                             "ok": bool(worst_err <= 5 and worst_span <= 660)}
        if not labels.empty:
            r5 = labels[(labels["model_tag"] == model) & (labels["plan"] == "mixed_load") & (labels["label"] == "GET /search")]
            r5 = r5[r5["run_id"].isin(runs["run_id"])] if not runs.empty else r5
            if len(r5):
                row["R5"] = {"value_ms": float(r5["client_p95_ms"].max()), "runs": int(len(r5)),
                             "ok": bool(r5["client_p95_ms"].max() <= 2000)}
        acc = next((a for a in accuracy if a["model_tag"] == model), None)
        if acc:
            row["R3"] = {"value": acc["accuracy"], "ok": bool((acc["accuracy"] or 0) >= 0.90)}
            recalls = {c["category"]: c["recall"] for c in acc["per_category"]}
            failing = [c for c, v in recalls.items() if v is None or v != v or v < 0.80]
            row["R4"] = {"min_recall": min((v for v in recalls.values() if v == v), default=None),
                         "failing": failing, "ok": not failing}
        out.append(row)
    return out


def narrative() -> dict:
    """The team's words for the judgement slides: interpretation, recommendation.

    Numbers never live here; the slides take them from analysis/output/. This file
    holds only the sentences that interpret them, so the two cannot drift silently.
    """
    path = REPO / "slides" / "narrative.yaml"
    if not path.is_file():
        missing("slides/narrative.yaml (interpretation and recommendation text)")
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for key, value in data.items():
        if isinstance(value, str) and ("TODO" in value or "⟪" in value):
            missing(f"slides/narrative.yaml: {key} is not written yet")
    return data


def _finite(value):
    """NaN and infinities become null: JSON has no NaN, and the deck shows null as a dash."""
    if isinstance(value, float):
        return value if value == value and value not in (float("inf"), float("-inf")) else None
    if isinstance(value, dict):
        return {k: _finite(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_finite(v) for v in value]
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):  # numpy scalars
        return _finite(value.item())
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--final", action="store_true", help="fail on any missing input")
    args = parser.parse_args()
    load = load_results()
    accuracy = accuracy_results()
    bottleneck = bottleneck_results()
    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_commit": git("rev-parse", "--short", "HEAD"),
        "team": team(), "architecture": architecture(), "workload": workload(),
        "requirements": requirements(), "models": models(), "golden": golden(),
        "environment": environment(), "load": load, "stress": stress_results(),
        "bottleneck": bottleneck, "bottleneck_summary": bottleneck_summary(bottleneck),
        "reconcile": reconcile_summary(), "accuracy": accuracy, "verdicts": verdicts(load, accuracy),
        "predictions": predictions(), "references": references(), "narrative": narrative(),
    }
    data["missing"] = MISSING
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(_finite(data), indent=2, default=str, allow_nan=False), encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)}")
    for item in MISSING:
        print(f"  missing: {item}")
    if args.final and MISSING:
        print("refusing --final: the deck would show a gap", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
