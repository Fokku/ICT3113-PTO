#!/usr/bin/env bash
#
# build_submission.sh -- from finished runs to Group10.pptx and the supporting files.
#
# Owner: Part 1 -- Yeo Kai Yuan (deck assembly).
#
# Runs, in order, on a checkout that already holds the evidence (results/ and
# logs/service/):
#   1. scripts/run_analysis.sh            every analysis output, from scratch
#   2. slides/collect_deck_data.py --final every figure the deck shows, from those outputs
#   3. node slides/build_deck.js           slides/Group10.pptx
#   4. submission/                         the deck plus the supporting files the brief lists,
#                                          and a zip of the supporting files for xSiTe
#
# Usage:
#   scripts/build_submission.sh [--draft]     # --draft builds even with gaps (amber PENDING panels)
#
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"
cd "$REPO_ROOT"
PY="${REPO_ROOT}/.venv/bin/python"
[[ -x "$PY" ]] || PY="$(command -v python3)"
FINAL=(--final)
[[ "${1:-}" == "--draft" ]] && FINAL=()

# 1. Analysis from scratch: a stale table from an earlier pass must not survive.
rm -rf analysis/output/reconcile analysis/output/load analysis/output/accuracy \
       analysis/output/stress analysis/output/bottleneck
scripts/run_analysis.sh

# 2-3. The deck.
"$PY" slides/collect_deck_data.py ${FINAL[@]+"${FINAL[@]}"}
( cd slides && [[ -d node_modules ]] || npm ci --silent )
node slides/build_deck.js slides/Group10.pptx

# 4. The submission folder (gitignored): the deck, and the supporting files the
# brief names -- golden set, prediction record (as frozen), protocol with its
# revisions, both independent label sheets, the agreement statistic.
OUT="submission"
rm -rf "$OUT" && mkdir -p "$OUT/Group10_supporting_files"
cp slides/Group10.pptx "$OUT/Group10.pptx"
S="$OUT/Group10_supporting_files"
cp golden/golden_set.csv "$S/"
git show golden-freeze:predictions/prediction_record.md > "$S/prediction_record.md"
cp predictions/outcomes.md "$S/prediction_outcomes.md"
cp labelling/protocol.md labelling/labeller_A.csv labelling/labeller_B.csv \
   labelling/agreement_report.txt labelling/disagreements.csv \
   labelling/resolutions.md labelling/resolutions.csv "$S/"
cat > "$S/README.txt" <<EOF
ICT3113 Assignment 1 -- Group 10 -- supporting files
Repository: https://github.com/Fokku/ICT3113-PTO  (golden-freeze tag: $(git rev-list -n 1 golden-freeze))

golden_set.csv            the golden test set: final labels for 200 tickets, by row_number (team rows 10000-10999)
prediction_record.md      the prediction record exactly as frozen (git show golden-freeze:predictions/prediction_record.md)
prediction_outcomes.md    every prediction against its measured outcome (Slide 11's full account)
protocol.md               the labelling protocol, with its revision log (R0-R5)
labeller_A.csv            independent label sheet A (Loh Wen Xuan)
labeller_B.csv            independent label sheet B (Jolie Ngai Ning Li)
agreement_report.txt      the inter-annotator agreement statistic (Cohen's kappa) and its per-category breakdown
disagreements.csv         every disagreement between the two sheets
resolutions.md / .csv     how each disagreement was resolved

Raw JMeter .jtl files and service logs are in the repository (results/, logs/service/), not in this zip.
Built $(date -u +%Y-%m-%dT%H:%MZ) from commit $(git rev-parse --short HEAD).
EOF
( cd "$OUT" && rm -f Group10_supporting_files.zip && zip -qr Group10_supporting_files.zip Group10_supporting_files )
ls -la "$OUT"
echo "build_submission: done. Upload $OUT/Group10.pptx and $OUT/Group10_supporting_files.zip to xSiTe."
