# `docs/environment/` — captured machine evidence

**What this directory is for.** It holds one generated text file per machine involved in a test, recording
what that machine *is*: CPU, memory, operating system and kernel, Docker, Ollama and JMeter versions, IP
addresses and the repository state at capture time. Slide 7 (Test Environment) is written from these files,
and they are also what the `service_host_info` and `load_generator_host_info` fields of every run's
`metadata.json` point at.

**Owner:** Part 5 — Koh Tong Wei.

**What "done" looks like.** There is one committed `<hostname>.txt` in this directory for **every** machine
that took part in a reported run — the triage service host, the Ollama host and the load generator — the
hostnames in those files are distinct from one another, and every hardware or version figure quoted on
Slide 7 can be pointed at a line in one of them.

**Feeds:** Slide 7 (Test Environment), and the environment half of Slide 8 (Playbook).

---

## 1. Run the capture on every machine

`scripts/capture_env.sh` is run **once per machine**, on that machine, with the role that machine plays:

```bash
# On the machine running the triage service container:
scripts/capture_env.sh --role service

# On the machine running Ollama:
scripts/capture_env.sh --role ollama

# On the machine running JMeter and scripts/run_accuracy.py:
scripts/capture_env.sh --role loadgen
```

Where one machine genuinely fills two of those roles — the service and Ollama on the same box is the normal
arrangement — run it once on that machine with the role that matters most for the hardware claim and say so
on the slide. `--role all` also exists, but it *declares that one machine runs everything*, and the script
writes a warning into the file saying so, because the brief does not accept latency measured with a
co-hosted load generator. Do not use `--role all` to mean "I could not decide".

The script contacts nothing except a three-second probe of `${OLLAMA_BASE_URL}/api/version`, runs no model,
times nothing, and never fails because a tool is missing: an absent tool is recorded as `not installed`,
which is itself a fact worth keeping.

## 2. Commit the output

```bash
git add docs/environment/<hostname>.txt
git commit -m "Capture test environment: <hostname> (<role>)"
```

One file per hostname. The file name is the machine's own `hostname`, reduced to letters, digits, dot, dash
and underscore. Commit it from the machine that produced it, or copy it across and commit it centrally —
either is fine, as long as the file that lands in the repository is the one the script wrote.

## 3. Do not hand-edit these files

They are regenerated in place: the script writes to a temporary file and moves it over the old one, so any
sentence you add is lost the next time anyone re-runs it. In particular, the narrative that the brief asks
for — the network between the machines, the factors that could make our measurements unrepresentative, and
how the results scale to the client's deployment — goes in `../test-environment.md` and **cites** these
files. The capture script prints a reminder to that effect in section 7 of every file it writes.

## 4. Re-capture when the machine changes

Re-run the capture, and commit the new version, whenever any of these happens before a reported run:

* a JMeter, Java, Docker, Ollama or kernel upgrade on that machine;
* a hardware change, including moving the service to a different machine;
* a change to `OLLAMA_NUM_PARALLEL`, `OLLAMA_MAX_LOADED_MODELS`, `OLLAMA_NUM_THREADS` or
  `OLLAMA_KEEP_ALIVE`, which the script records from the environment it is run in.

The file records its own `Captured at (UTC)` and the repository commit it was taken at, so a stale capture is
visible rather than misleading. A capture taken *after* the runs it describes is still usable evidence; a
capture taken on different hardware is not.

## 5. If two machines share a hostname

This matters more than it looks. The file name is derived from the hostname, so two machines called
`ubuntu` or `DESKTOP-ABC123` would write to the same path and the second capture would silently overwrite the
first. Worse, `load_generator_host_info.hostname` in every run's `metadata.json` also comes from the
operating system's hostname, so if the load generator and the service host report the same name, the
repository contains no evidence that they were different machines — which is exactly the claim Slide 7 has to
make.

**Preferred fix: give the machines distinct hostnames before the first reported run.** It costs a minute and
it fixes the evidence problem at source:

```bash
# Linux (systemd):
sudo hostnamectl hostname ict3113-loadgen
# macOS:
sudo scutil --set HostName ict3113-loadgen
```

Then re-run the capture on that machine and commit the new file. Delete the file written under the old
hostname in the same commit, so the directory does not appear to describe a machine that no longer exists.

**If a hostname cannot be changed** (a shared lab machine, a managed laptop), then capture to a scratch
directory and place the file under a name that distinguishes the role, and say in the commit message that the
name was assigned by hand:

```bash
scripts/capture_env.sh --role loadgen --out-dir /tmp/envcap
cp /tmp/envcap/<hostname>.txt docs/environment/loadgen-<hostname>.txt
```

In that case the "two distinct hostnames" evidence is gone, and Slide 7 must establish the separate-machine
claim another way. Use the two facts that survive: the **IPv4 addresses** recorded in section 7 of each
capture file, and the `service_url` field of every run's `metadata.json`, which is the address JMeter
actually posted to and must not be `localhost` or `127.0.0.1`. Say in the write-up which of the two you are
relying on.

**Our two machines, and the capture each needs.** Machine 1, the service host, is Yeo Kai Yuan's desktop and
runs both the triage service and Ollama: capture it with `--role service` and say on Slide 7 that it is also
the Ollama host. Machine 2, the load generator, is a team member's laptop: capture it with `--role loadgen`.
Neither capture exists yet.

`TODO(Part 5 — Koh Tong Wei): after the two captures are committed, copy their hostnames and figures into the
table at the top of ../test-environment.md, and check that the two hostnames differ.`
