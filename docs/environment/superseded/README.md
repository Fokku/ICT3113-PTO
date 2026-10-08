# Superseded environment captures

These are the `scripts/capture_env.sh` outputs for the first test environment, kept as history:

| File | Machine | Role it was captured for |
|---|---|---|
| `tw-Service.txt`, `tw-Ollama.txt` | `tw` — Intel Core Ultra 7 155H laptop, Ubuntu 24.04 on WSL2 | triage service and Ollama |
| `kthgoat-Loadgen.txt` | `kthgoat` — Intel Core i5-14400F desktop, Ubuntu 26.04 on WSL2 | JMeter load generator |

Both machines became unavailable on 8 October 2026, before any reported measurement. The only real run made
on `tw` (a `llama3.2:1b` accuracy run on 8 October) predates the prediction record and is excluded; see
`results/excluded/EXCLUDED.md`. The rehearsals made on these machines are logged in `docs/run-log.md`.

**No reported number comes from these machines.** The environment every reported run used is captured in
the files one level up and described in `docs/test-environment.md`.
