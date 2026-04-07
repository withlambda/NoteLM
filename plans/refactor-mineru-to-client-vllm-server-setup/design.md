# Design — MinerU HTTP Client with Local vLLM Server

## Task Execution Order

```text
Task 01 (Select Server Orchestration Path)
  └─→ Task 02 (Refactor Runtime Wiring in Handler/Settings)
        └─→ Task 03 (Align Dependencies + Docker Model Setup)
              └─→ Task 04 (Tests, Validation, and Documentation)
```

Task 01 is a hard decision gate because both implementation and Docker/runtime assumptions depend on the chosen server startup method.

## Context from MinerU Documentation and CLI Code

1. MinerU supports a lightweight client mode for VLM HTTP requests:
   - `mineru -b vlm-http-client -u http://127.0.0.1:30000`
2. MinerU CLI starts a temporary local `mineru-api` service automatically when `api_url` is omitted:
   - `mineru/cli/client.py:852-875` creates `LocalAPIServer`, starts it, and waits for `/health`.
3. `mineru/cli/api_client.py:118-159` implements `LocalAPIServer.start()` by launching `python -m mineru.cli.fast_api`.
4. `mineru/cli/fast_api.py:927-965` forwards `backend` and `server_url` into `do_parse` / `aio_do_parse`, so MinerU’s API layer is the ready-to-use parse orchestrator.
5. MinerU can run an OpenAI-compatible VLM server:
   - `mineru-openai-server --engine vllm --port 30000`
6. `mineru/cli/vlm_server.py:27-58` shows `mineru-openai-server` is a thin wrapper around the VLM model server entrypoint, not the parse-task orchestrator.
7. MinerU treats `--url/-u` as the OpenAI-compatible backend URL in HTTP-client backends.
8. MinerU model source selection is controlled by `MINERU_MODEL_SOURCE` (including `local`).
9. MinerU allows selecting a served model via `MINERU_VL_MODEL_NAME` when multiple models exist on the server.
10. `mineru/cli/client.py:603-613` plans non-pipeline work as one document per task and submits those tasks with bounded concurrency to a shared service, which is the key pattern to mirror in NoteLM.

## Current NoteLM Gap

- `handler.py` currently calls MinerU parsing with `backend="pipeline"`.
- `requirements.txt` currently installs `mineru[pipeline]`.
- `Dockerfile` currently downloads both:
  - `opendatalab/PDF-Extract-Kit-1.0` (pipeline)
  - `opendatalab/MinerU2.5-2509-1.2B` (vlm)
- `handler.py` currently normalizes MinerU outputs into a NoteLM-specific markdown/image layout that downstream post-processing already depends on.

This hardwires pipeline dependencies and model downloads that are not required for `vlm-http-client` parsing.

Task execution must re-read the current working-tree versions of `handler.py`, `Dockerfile`, `requirements.txt`, and `check_dependencies.py` before implementation because these files are already active integration hotspots and should be treated as the merge baseline rather than assumed to match an older clean revision.

## Target Runtime Flow

```text
RunPod Job
  ├─ 1) Start local OpenAI-compatible VLM server (background)
  │      - preferably via `mineru-openai-server`
  │      - wait until /health is ready
  ├─ 2) Start local MinerU parse orchestration layer if Option A is selected
  │      - preferably via MinerU `LocalAPIServer` / `mineru-api`
  │      - wait until /health is ready
  ├─ 3) Run MinerU parse requests with backend=vlm-http-client
  │      - pass OpenAI-compatible `server_url` to MinerU (`-u` / equivalent function arg)
  │      - pass model name (`MINERU_VL_MODEL_NAME`) when needed
  │      - preserve or intentionally redefine the NoteLM downstream parse-output contract
  ├─ 4) Stop the MinerU parsing VLM server and confirm handoff readiness
  │      - wait for process exit / cleanup completion
  │      - ensure VRAM is released before starting any other VLM server
  ├─ 5) Start NoteLM’s own post-processing VLM server only if still needed
  │      - keep this as a separate post-processing server lifecycle owned by NoteLM
  │      - reuse the same shared `vllm_server.py` server-management abstraction
  │      - never overlap with the MinerU parsing VLM server lifecycle
  └─ 6) Shutdown remaining services and cleanup
```

### Runtime Ownership Rules

- Treat the MinerU parsing VLM server and NoteLM post-processing VLM server as two separate sequential lifecycles that must never run in parallel.
- The new external OpenAI-compatible server exists only for MinerU parsing; it is not a shared live server for NoteLM post-processing.
- MinerU parsing runs first. Its VLM server must be shut down completely and its VRAM released before NoteLM starts any post-processing VLM server.
- If Option A remains feasible, `mineru-api` is the single owner of parse-task concurrency. NoteLM must not preserve an outer multiprocessing/file-level parse pool around MinerU submissions.
- If Option A remains feasible, Task 01 must lock in full delegation through one MinerU orchestration entrypoint that accepts the job input directory; downstream tasks must not re-implement MinerU task submission inside NoteLM.
- If Task 01 rejects Option A, the fallback decision must explicitly constrain outer parse parallelism to `1` (or a stricter proven-safe limit) and document why full delegation to `mineru-api` was not feasible.
- Task 01 must document the exact stop-before-start handoff contract: process owner, shutdown signal/wait behavior, timeout, `gc.collect()`/CUDA-cache cleanup step, cooldown duration, startup retry budget for the next server, and failure behavior if cleanup does not complete.
- NoteLM must centralize both VLM-serving roles behind one shared server-management abstraction in `vllm_server.py` (creating that module if it does not already exist, and adapting existing `vllm_worker.py` logic to use it) so startup, health checks, shutdown, and error handling follow one contract.
- The shared `vllm_server.py` manager owns only VLM-serving processes. `mineru-api` lifecycle ownership must be documented separately and should remain under MinerU-native helpers or an explicitly separate wrapper rather than being silently folded into the shared VLM manager.
- The served model name for MinerU parsing must have one source of truth and must be mapped explicitly to whichever server implementation is selected:
  - MinerU official server path: document the model-selection contract used by `mineru-openai-server`.
  - NoteLM fallback `vllm serve` path: document `--served-model-name` alignment with `MINERU_VL_MODEL_NAME`.
- Task 01 must record the observed served-model identifier from the selected server path using an explicit proof step rather than assuming the weight source string is the request-time model name.
- The selected runtime path must preserve or intentionally redefine the NoteLM parse-output artifact contract consumed downstream, including markdown-path resolution, extracted-image placement, and deterministic mapping from each input file to its processed output artifact.
- Task 01 must establish one canonical removed-legacy-keys list and one consistent rejection mode so settings validation, job-input extraction, tests, and README all describe the same breaking configuration behavior.

## Option Analysis (Task 01 Decision)

### Option A — MinerU-native parse orchestration + official OpenAI server

**Mechanism**
- Start a local `mineru-api` service using MinerU’s own helpers (`LocalAPIServer` / `mineru.cli.fast_api`).
- Start `mineru-openai-server --engine vllm ...` for the OpenAI-compatible model-serving endpoint used by `vlm-http-client`.
- Submit parse work through MinerU’s HTTP orchestration layer, mirroring how `mineru` CLI manages health checks, task submission, and bounded concurrency.

**Pros**
- Closest to MinerU-supported deployment path.
- Reuses MinerU’s own startup/health/task-management model instead of re-implementing it in NoteLM.
- Gives a clearer answer to the concurrency question because MinerU already uses one shared API service plus bounded task concurrency for non-pipeline backends.

**Cons**
- Introduces an additional local service (`mineru-api`) into NoteLM if direct function calls were previously sufficient.
- Requires explicit mapping between NoteLM job lifecycle and MinerU API task lifecycle.

### Option B — Direct MinerU parse calls + official OpenAI server

**Mechanism**
- Keep NoteLM calling MinerU parse functions directly (`do_parse` / `aio_do_parse`).
- Replace `backend="pipeline"` with `backend="vlm-http-client"` and pass `server_url`.
- Start the OpenAI-compatible model-serving endpoint using MinerU’s official `mineru-openai-server` entrypoint.

**Pros**
- Smaller refactor than adopting the full MinerU API orchestration layer.
- Still stays close to MinerU’s supported server entrypoint for model serving.

**Cons**
- Leaves more orchestration responsibility inside NoteLM.
- Does not reuse MinerU’s own local API task-management layer.

### Option C — NoteLM-managed local `vllm serve` via shared `vllm_server.py`

**Mechanism**
- Reuse/adapt existing `vllm_worker.py` startup internals behind the shared `vllm_server.py` manager to start plain `vllm serve`.
- Point MinerU HTTP-client parsing at that endpoint.

**Pros**
- Maximum control over custom `vllm serve` flags already implemented in NoteLM.

**Cons**
- Furthest from MinerU’s own supported setup.
- Most likely to diverge from MinerU behavior over time.

## Recommended Baseline

Unless Task 01 produces a documented feasibility blocker, start with **Option A** for implementation because it matches MinerU’s own supported setup most closely:
- `mineru` CLI already uses a self-managed local `mineru-api` process when no external API URL is provided.
- `mineru-openai-server` is the official OpenAI-compatible VLM-serving entrypoint.
- MinerU’s non-pipeline concurrency model is already centered on one shared service with bounded task submission, which is the clearest answer to the current NoteLM concurrency ambiguity.
- It is the only currently identified path that can cleanly delegate parse-task concurrency to `mineru-api`, which is the preferred way to avoid nested parallelism and VRAM contention.

Keep **Option B** as the first fallback if adopting the full local API layer is too invasive for NoteLM. Reserve **Option C** for last resort only.

### Concurrency Baseline for Downstream Tasks

- Downstream tasks should assume that the preferred outcome is: one NoteLM job orchestrates one `mineru-api` lifecycle, and `mineru-api` owns parse-task concurrency.
- Downstream tasks should treat MinerU server-side orchestration as the preferred concurrency mechanism and should not preserve NoteLM-owned document-level parse scheduling when Option A is selected.
- `handler.py` should not keep its current outer multiprocessing-per-file MinerU execution model if Option A is selected.
- If fallback Option B or C is chosen, Task 01 must leave a written proof that the fallback does not recreate nested parse concurrency and must state the exact outer-parallelism cap.
- Downstream tasks should remove legacy parse-concurrency configuration knobs rather than keep compatibility aliases for the old pool-based contract.

## Task 01 Decision Record Requirements (`Selected Integration Contract`)

Task 01 must leave behind an explicit decision record in this file before downstream implementation starts. The record must include:

1. Selected option (`A`, `B`, or `C`) and rejected options.
2. Exact commands/functions that downstream code will call for:
   - OpenAI-compatible VLM server startup
   - parse orchestration startup/submission
   - health checks and cleanup.
3. Exact environment variables, config keys, defaults, and ownership rules for:
   - `api_url` / local `mineru-api`
   - OpenAI-compatible `server_url`
   - served model name / `MINERU_VL_MODEL_NAME`
   - `MINERU_MODEL_SOURCE`
   - timeout values.
4. Exact served-model-name proof:
   - the observed request-time model identifier exposed by the selected serving path
   - how that identifier maps to `MINERU_VL_MODEL_NAME`.
5. Dependency proof:
   - exact candidate MinerU `3.0.7` requirement string
   - proof method for required modules/scripts (`import`, CLI `--help`, or subprocess smoke check).
6. Mandatory non-parallel handoff contract for MinerU parsing vs. NoteLM post-processing VLM usage, including ports, shutdown ownership, VRAM-release guardrails, and failure behavior.
7. Exact shared `vllm_server.py` class/interface that will start both VLM-serving roles, with an explicit statement that `mineru-api` lifecycle ownership remains outside that abstraction, and how it maps to MinerU’s official parsing-server entrypoints versus NoteLM’s retained post-processing server behavior.
8. Exact parse output artifact contract after MinerU parsing:
   - markdown-path discovery
   - extracted-image placement
   - mapping from each input file to the artifact consumed by post-processing.
9. Exact concurrency owner and task-partitioning decision:
   - whether MinerU’s client/API path fully owns parse-task concurrency
   - the exact full-delegation entrypoint used when Option A is selected
   - which legacy MinerU settings are removed or explicitly rejected so they cannot reintroduce nested concurrency.
10. Canonical removed-legacy-keys rejection contract:
   - exact removed keys
   - exact layer and failure mode used to reject them.

## Selected Integration Contract (Task 01 Output Template)

- `Selected option:`
- `Rejected options + rationale:`
- `Parse orchestration entrypoint:`
- `OpenAI-compatible VLM server entrypoint:`
- `Health endpoints + readiness checks:`
- `Concurrency owner:` Prefer MinerU’s client/API server-side orchestration unless Task 01 documents a feasibility blocker.
- `Task partitioning:`
- `Config/env source of truth:` backend, `api_url`, `server_url`, `MINERU_MODEL_SOURCE`, `MINERU_VL_MODEL_NAME`, ports, timeouts.
- `Served model identifier proof:`
- `Server ownership split:` MinerU external parsing server only; NoteLM retains its own post-processing server lifecycle.
- `Shared vllm_server.py manager contract:` owns VLM-serving processes only; `mineru-api` lifecycle is documented separately.
- `Parse output artifact contract:`
- `Shutdown / VRAM-release handoff guardrail:`
- `Removed/rejected legacy settings:`
- `Legacy-key rejection mode:`
- `Dependency proof method + exact MinerU 3.0.7 requirement string:`

## Files Expected to Change During Implementation

- `handler.py`
  - Replace hardcoded MinerU `pipeline` backend with configurable HTTP-client backend.
  - Replace the current multiprocessing-based per-file parse invocation with one MinerU-native orchestration entrypoint if Option A is selected; do not keep the existing pool model or a mirrored NoteLM submission layer.
  - Preserve or intentionally redefine the current markdown/image output contract consumed by downstream post-processing and document the resulting artifact mapping explicitly.
  - Remove legacy parse-pool settings/job-input handling that only existed to support the old pipeline-oriented contract.
  - Wire in API URL, OpenAI `server_url`, model settings, and lifecycle ordering.
- `vllm_server.py`
  - Introduce this module if it does not already exist, and implement a shared server-management class that can start/stop both the MinerU parsing VLM server role and the NoteLM post-processing VLM server role through one interface while keeping them as separate sequential server lifecycles.
  - Enforce the stop-before-start handoff so the second role cannot start until the first role has exited and VRAM-release checks/guardrails have passed.
- `mineru-api` lifecycle wrapper/config
  - Keep `mineru-api` lifecycle management outside the shared `vllm_server.py` manager boundary and document whether MinerU-native helpers or a separate thin wrapper own that process.
- `vllm_worker.py`
  - Retain NoteLM’s own post-processing server lifecycle and delegate any remaining local `vllm serve` startup logic to the shared `vllm_server.py` abstraction if post-processing still needs a dedicated serving phase.
- `settings.py`
  - Add/confirm MinerU HTTP-client settings (`backend`, parse API URL/local API mode, OpenAI `server_url`, `MINERU_MODEL_SOURCE`, optional model name).
  - Remove or explicitly reject legacy outer-concurrency settings such as `mineru_workers` so they cannot reintroduce nested parse parallelism under the preferred MinerU API/client server-side concurrency path.
  - Materialize one canonical removed-legacy-keys list and one consistent rejection mode.
- `requirements.txt`
  - Align to MinerU `3.0.7`.
  - Switch from `mineru[pipeline]` to the minimal MinerU `3.0.7` package/extras compatible with the chosen HTTP-client orchestration path.
- `Dockerfile`
  - Remove pipeline model download command.
  - Keep only MinerU VLM model download (`opendatalab/MinerU2.5-2509-1.2B`).
  - Keep `mineru.json` aligned for local model source.
- `check_dependencies.py`
  - Remove pipeline-only assertions that are no longer valid.
  - Add checks for the official MinerU modules/scripts used by the selected path (`mineru.cli.fast_api`, `mineru.cli.vlm_server`, `mineru.cli.client`, or equivalent) using the proof method selected in Task 01.
- Tests under `test/`
  - Update existing settings extraction tests and add new handler orchestration tests for HTTP-client mode, URL/model wiring, lifecycle ordering, and cleanup behavior.
- `README.md`
  - Document startup and configuration for the MinerU external parsing server + client path and the retained separate NoteLM post-processing server path.

## Configuration and Dependency Impacts

1. **Environment Variables / Service Arguments**
   - MinerU-side: `MINERU_MODEL_SOURCE=local`, `MINERU_VL_MODEL_NAME`, and any `mineru-api` runtime variables required for bounded concurrency.
   - NoteLM-side: runtime host/port/model selection values for the local API and for the retained post-processing server lifecycle.
   - Task 03 should materialize this into a dependency/config matrix covering requirement strings, CLI/modules to verify, environment/config keys, removed legacy keys, model assets, and `check_dependencies.py` proof strategy.
2. **Model Storage**
   - Keep only VLM model artifacts needed by MinerU in Docker image for MinerU parsing requirement.
3. **No Silent Fallbacks**
   - If server fails to start or model is missing, fail fast with explicit logs.
4. **Version Alignment**
   - NoteLM package pins and Docker/runtime assumptions must match MinerU `3.0.7` semantics, not the currently pinned `3.0.1` behavior.

## Validation Strategy

1. Unit tests for settings extraction and MinerU invocation argument construction, including backend/API URL/OpenAI `server_url`/`MINERU_MODEL_SOURCE`/model-name coverage and explicit rejection of removed legacy settings.
2. New handler orchestration tests plus targeted integration-style test/mocked flow ensuring:
   - official MinerU server helpers/entrypoints are selected before any custom NoteLM fallback
   - server start is invoked before MinerU parse
   - backend is `vlm-http-client`
   - API URL vs. OpenAI `server_url` semantics are passed correctly
   - model name is passed correctly
   - the observed served-model identifier proof aligns with the chosen server path and config defaults
   - `mineru-api` owns parse-task concurrency when Option A is selected and NoteLM does not keep an outer parse multiprocessing layer
   - the parse output artifact contract remains compatible with downstream post-processing or is intentionally redefined and documented
   - the MinerU parsing VLM server is stopped and its cleanup/VRAM-release guardrail completes before the post-processing VLM server is started
   - both VLM-serving phases are started through the same shared `vllm_server.py` manager interface
   - `mineru-api` lifecycle is not silently pulled under the shared VLM manager boundary
   - failure propagation is explicit for OpenAI server startup failure, `mineru-api` startup failure, health timeout, and parse-phase failure after startup
   - parse failure still triggers deterministic cleanup of the parsing VLM server and blocks post-processing VLM startup unless explicitly intended by the selected contract
   - no silent fallback to `pipeline` occurs
   - removed legacy settings do not continue to work through compatibility shims.
3. Build-level check:
   - NoteLM installs MinerU `3.0.7` with the selected extras/requirement string
   - required MinerU modules/scripts are proven available using the Task 01-selected validation method
   - the selected MinerU command/function path is proven minimally usable after install via one bounded smoke check, not just importable
   - Docker no longer downloads `PDF-Extract-Kit-1.0`
   - Docker still downloads `MinerU2.5-2509-1.2B`
   - if multiple Docker-based checks are required, prefer reusing the project `Dockerfile`; only create a temporary validation image when additional validation-only tooling is required
   - if a temporary validation image is needed, place its orchestration assets under `plans/refactor-mineru-to-client-vllm-server-setup/validation/`
   - if multiple checks execute inside that container, run them via one mounted orchestration script so they can execute sequentially within a single container start
   - persist all container-run evidence into one mounted results file under `plans/refactor-mineru-to-client-vllm-server-setup/validation/` that remains available after container shutdown.
4. Runtime smoke check in container/logs for health readiness and successful parse path using the chosen MinerU-native orchestration flow.
   - Keep this smoke check minimal and deterministic: one bounded sample run with explicit evidence for readiness ordering, parse-server shutdown, VRAM-release handoff, and endpoint usage.
   - Reuse the prepared validation container/image and the same mounted orchestration/results-file pattern whenever this smoke check shares the same Docker environment as other validations.
5. Documentation check:
   - ensure README and operational notes no longer imply `PDF-Extract-Kit-1.0` is required for MinerU parsing
   - ensure the final docs reflect the selected path’s exact runtime contract.
