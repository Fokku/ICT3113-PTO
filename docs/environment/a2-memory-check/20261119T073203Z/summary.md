# Assignment 2 memory check

Run 2026-11-19T07:39:06Z on `omarchy` by `scripts/memory_check_a2.py`. Ollama 0.34.3. Host RAM 31.3 GiB. Ollama container limits (`docker inspect` HostConfig.Memory, NanoCpus): memory none (the host's RAM), CPU none (all host CPUs). Inference settings recorded, not changed: see `ollama_env.txt`.

Procedure per pair (brief, Step 2): restart the Ollama container, send 3 hand-written dev tickets to each model alternately (small, large, small, large, ...) with the unchanged classification prompt, then `ollama ps` inside the container. A pair **fits** when `ollama ps` lists both models after the last call and no call after each model's first paid a reload (`load_duration` > 1000.0 ms).

| Small model | Large model | `ollama ps` lists both | Reloads after first load | Resident size (GiB) | Verdict | Evidence |
|---|---|---|---|---|---|---|
| `llama3.2:1b-instruct-q4_K_M` | `qwen2.5:7b` | yes | 0 | 5.65 | **fits** | `docs/environment/a2-memory-check/20261119T073203Z/llama3.2-1b-instruct-q4_K_M__qwen2.5-7b/ollama_ps.txt` |
| `llama3.2:3b` | `qwen2.5:7b` | yes | 0 | 7.10 | **fits** | `docs/environment/a2-memory-check/20261119T073203Z/llama3.2-3b__qwen2.5-7b/ollama_ps.txt` |
| `granite4:3b` | `qwen2.5:7b` | yes | 0 | 7.05 | **fits** | `docs/environment/a2-memory-check/20261119T073203Z/granite4-3b__qwen2.5-7b/ollama_ps.txt` |

## `ollama ps` output, per pair

**llama3.2:1b-instruct-q4_K_M + qwen2.5:7b**

```
NAME                           ID              SIZE      PROCESSOR    CONTEXT    UNTIL              
qwen2.5:7b                     845dbda0ea48    5.1 GB    100% CPU     4096       4 minutes from now    
llama3.2:1b-instruct-q4_K_M    22bc6b92eb01    1.0 GB    100% CPU     4096       4 minutes from now
```

**llama3.2:3b + qwen2.5:7b**

```
NAME           ID              SIZE      PROCESSOR    CONTEXT    UNTIL              
qwen2.5:7b     845dbda0ea48    5.1 GB    100% CPU     4096       4 minutes from now    
llama3.2:3b    a80c4f17acd5    2.6 GB    100% CPU     4096       4 minutes from now
```

**granite4:3b + qwen2.5:7b**

```
NAME           ID              SIZE      PROCESSOR    CONTEXT    UNTIL              
qwen2.5:7b     845dbda0ea48    5.1 GB    100% CPU     4096       4 minutes from now    
granite4:3b    89962fcc7523    2.5 GB    100% CPU     4096       4 minutes from now
```

