# Slide drafts — Part 1 (Yeo Kai Yuan): Slides 2 and 5

Drafts handed to Part 5 — Koh Tong Wei for `Group10_A2.pptx` (`../outline_a2.md`, `../../TODO_A2.md` §1.6).
They hold content and sources only: Part 5 owns the layout and assembly.

| File | Slide | Status |
|---|---|---|
| [`slide2_cascade_design.md`](slide2_cascade_design.md) | 2 — Cascade design (Part 1's half: the diagram and the memory evidence; Part 2 owns the rule, settings and "why") | Structure drafted. The model pair, memory evidence and settings are filled in from the files named once they exist. |
| [`cascade_diagram.py`](cascade_diagram.py) → `cascade_diagram.png` / `.svg` | 2 — the diagram | Drawn from `service/cascade.py` (the settings' literal conditions), so the picture always matches the running code. Re-run it after the settings are written in. |
| [`slide5_speed_results.md`](slide5_speed_results.md) | 5 — Speed results | Structure drafted, with every figure mapped to its column in `analysis/output/speed_a2/`. The numbers come after the A2 gate and the runs. |

Regenerate the diagram once Part 2's settings are in `service/cascade.py` and the memory check has named the
pair:

```bash
python slides/drafts_a2/cascade_diagram.py --small <small tag> --large qwen2.5:7b
```
