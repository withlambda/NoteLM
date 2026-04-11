# Requirements — Refactor MinerU to HTTP Client + vLLM Server Setup

## Functional Requirements

### FR-1: MinerU Parsing Must Use HTTP Client Mode
- NoteLM must run MinerU with `backend="vlm-http-client"` (or equivalent CLI/backend wiring) instead of `pipeline` for the MinerU parsing phase.
- MinerU requests must be sent to a configurable OpenAI-compatible endpoint URL.
- When the MinerU-native API/client path is feasible, NoteLM must delegate parse-task scheduling/concurrency to MinerU’s server-side orchestration instead of layering an outer multiprocessing pool around MinerU submissions.
- The refactor must remove the current NoteLM parse multiprocessing contract rather than preserve it behind compatibility switches or fallback aliases.
- The refactor must preserve or intentionally redefine the parse output artifact contract consumed by downstream NoteLM post-processing, including markdown-path resolution, extracted-image placement, and one deterministic processed-output mapping per input file.

### FR-2: MinerU vLLM Server Must Be Started in Background for Parsing
- The runtime must support launching a local vLLM OpenAI-compatible server before MinerU parsing begins.
- MinerU parsing must wait for server health readiness before sending requests.
- The server lifecycle must be deterministic (start once per job/process scope, clean shutdown, explicit timeout/error path).
- The plan must distinguish between the parse-orchestration API endpoint and the OpenAI-compatible VLM `server_url` endpoint when both are used.
- The new external OpenAI-compatible server is for MinerU parsing only; NoteLM post-processing must keep its own separate server lifecycle rather than reusing the MinerU parsing server as a shared live process.
- Any fallback path that cannot delegate concurrency entirely to `mineru-api` must explicitly document why that delegation was infeasible and how NoteLM constrains replacement outer parallelism to avoid nested parallelism and VRAM contention.
- If NoteLM keeps a separate post-processing VLM-serving phase, the MinerU parsing vLLM server must be stopped completely and its VRAM released before the post-processing vLLM server is started.
- The MinerU parsing vLLM server and the post-processing vLLM server must never run in parallel.
- The plan must require one shared server-management abstraction in `vllm_server.py` to start, health-check, stop, and hand off both VLM-serving roles only; `mineru-api` lifecycle ownership must be documented separately and must not be silently folded into that abstraction.
- The plan must define the VRAM-release handoff rule concretely as: parsing-server process exit is observed, cleanup hooks run (`gc.collect()` plus CUDA cache cleanup when available), a configured cooldown elapses, and the post-processing server start must fail if the parse server is still alive or the next server does not become ready within the configured retry budget.

### FR-3: MinerU Dependency Footprint Must Be Reduced
- `requirements.txt` must not require `mineru[pipeline]` for the MinerU parsing path.
- The selected MinerU package/version must support `vlm-http-client` usage documented by MinerU.
- The selected package extras must be the minimum set needed for the chosen MinerU-native orchestration path while preserving official scripts/functions used by NoteLM.

### FR-4: Docker Build Must Stop Downloading Pipeline Model Bundle for MinerU
- `Dockerfile` must stop downloading `opendatalab/PDF-Extract-Kit-1.0` for MinerU usage.
- Docker build must download only `opendatalab/MinerU2.5-2509-1.2B` for MinerU VLM parsing needs.
- Generated `mineru.json` must keep a valid `vlm` model path for local MinerU model source usage.

### FR-5: MinerU Model Routing Must Be Explicit
- Runtime configuration must allow setting the model name used by MinerU HTTP client requests (e.g., via `MINERU_VL_MODEL_NAME`).
- Default model configuration for MinerU parsing must point to `opendatalab/MinerU2.5-2509-1.2B` unless explicitly overridden.
- Task 01 must prove the actual served model identifier exposed by the selected OpenAI-compatible serving path and record how that identifier maps to `MINERU_VL_MODEL_NAME`; the plan must not assume the weight source string is the request-time model name without proof.

### FR-6: Implementation Must Prefer MinerU-Native Orchestration with Approved Fallbacks
- Preferred Path A: Reuse MinerU’s own orchestration helpers first — `mineru.cli.api_client.LocalAPIServer` / `mineru-api` for parse-task orchestration plus `mineru-openai-server` (`mineru.cli.vlm_server.openai_server`) for the OpenAI-compatible model server, with full delegation through one MinerU orchestration entrypoint rather than a NoteLM-managed mirror of MinerU task submission.
- Fallback Path B: If Path A is not feasible in NoteLM, use MinerU’s parse functions directly (`do_parse` / `aio_do_parse`) with `backend="vlm-http-client"` while still using MinerU’s official OpenAI server entrypoint.
- Last-resort Path C: Start a compatible local `vllm serve` process in NoteLM only if MinerU-provided server/client helpers cannot satisfy the requirements, and route that fallback through the shared `vllm_server.py` abstraction rather than a separate standalone process manager.
- The final implementation must document the chosen path, rejected alternatives, rationale, exact commands/functions to call, required environment variables, health endpoints, timeout values, the MinerU-only external server ownership decision, the retained NoteLM post-processing server ownership decision, the shared `vllm_server.py` class/interface used to manage both VLM-serving roles, and the single source of truth for API host/port, OpenAI server host/port, and served model name.

### FR-7: NoteLM Must Align to MinerU 3.0.7
- NoteLM must update its MinerU dependency and related assumptions from `3.0.1` to `3.0.7`.
- The plan must verify that the selected `3.0.7` package extras still provide all required scripts/modules for the chosen integration path.

## Non-Functional Requirements

### NFR-1: Explicit Breaking Configuration Behavior
- The refactor may intentionally break the current MinerU configuration contract instead of preserving compatibility with legacy pipeline-era settings.
- New MinerU HTTP-client settings must have clear defaults and validation.
- Configuration must clearly separate any `mineru-api` base URL from the OpenAI-compatible VLM `server_url` consumed by HTTP-client backends.
- The configuration model must explicitly cover MinerU backend selection, local/remote parse API routing, OpenAI-compatible `server_url`, `MINERU_MODEL_SOURCE`, and `MINERU_VL_MODEL_NAME`.
- Deprecated MinerU job-input fields and settings tied to the old NoteLM multiprocessing parse path should be removed or rejected explicitly rather than silently mapped forward.
- The plan must establish one canonical removed-legacy-keys list and one consistent rejection mode for those keys across settings validation, job-input extraction, tests, and documentation.

### NFR-2: Deterministic Startup and Failure Modes
- If vLLM server startup fails, MinerU parsing must fail fast with actionable logs.
- No silent fallback to unavailable backends.

### NFR-3: Build Reproducibility
- MinerU, vLLM, and related package versions remain pinned as required by project policy.
- Docker model download commands must be deterministic and non-interactive.

### NFR-4: Testability
- Settings extraction and MinerU invocation behavior must be covered by automated tests.
- Dependency checks and startup assumptions must be validated by targeted checks.
- Automated coverage must include handler control-flow ordering, failure propagation, and explicit proof that NoteLM does not silently fall back to `pipeline`.
- Automated coverage must prove that MinerU parsing uses the external MinerU-facing server path while NoteLM post-processing continues to use its own server path under the same sequential handoff contract.
- Automated coverage must prove the strict VLM-server handoff: MinerU parsing server shutdown completes and VRAM is considered released before post-processing server startup is attempted, with no overlap between the two processes.
- Automated coverage must prove that removed legacy MinerU settings and old parse-pool controls are no longer accepted through compatibility aliases.
- Automated coverage must prove that the downstream parse output artifact contract remains valid after the refactor, including markdown discovery, image placement, and input-to-output mapping used by post-processing.
- When Docker-based validation is needed for multiple checks, the plan must require an economical test harness: pre-download required test dependencies in a temporary/prepared Dockerfile, run the in-container checks sequentially within one container start, and persist consolidated results through a single mounted output file.

## Edge Cases and Pitfalls

1. **Server Port Conflicts**
   - Local vLLM port may already be in use; configuration must support override or fail clearly.
2. **Server Ready vs. Process Started Race**
   - MinerU requests must not run before OpenAI-compatible `/health` readiness is confirmed.
3. **Model Name Mismatch**
   - If served model name and `MINERU_VL_MODEL_NAME` differ, MinerU requests may fail; mapping must be explicit.
4. **Model Source Configuration Drift**
   - `MINERU_MODEL_SOURCE=local` must align with `mineru.json` paths available inside the container.
5. **Residual Pipeline Assumptions**
   - Any remaining `backend="pipeline"` or pipeline-only dependency checks must be removed or gated.
6. **Shared-Server Concurrency**
   - MinerU’s own non-pipeline orchestration uses one shared service with bounded task concurrency rather than one VLM server per document; NoteLM must avoid GPU oversubscription when adapting this pattern and should make `mineru-api` the single concurrency owner whenever feasible.
7. **API URL vs. OpenAI Server URL Confusion**
   - `api_url` / local `mineru-api` base URL and `server_url` / OpenAI-compatible VLM endpoint are different contracts and must not be conflated.
8. **Dual-Server Resource Contention**
   - If MinerU parsing and NoteLM post-processing both want local VLM servers, the implementation must enforce a strict stop-before-start handoff so they never coexist, and it must define how shutdown completion / VRAM release is verified before the second server starts.
9. **Legacy NoteLM Worker Settings**
   - Legacy NoteLM settings such as `mineru_workers` should not survive as compatibility controls for the new HTTP-client path; the plan should remove or explicitly reject them if they imply the old outer parse parallelism model.
10. **Concurrency Ownership Drift**
   - When the MinerU API/client path is selected, server-side MinerU orchestration must remain the preferred owner of parse-task concurrency; plan artifacts must not leave room for reintroducing NoteLM-owned file-level parallelism by default.

## Definition of Done

1. NoteLM no longer hardcodes MinerU `pipeline` backend in the parsing path.
2. MinerU parsing runs through `vlm-http-client` against a local OpenAI-compatible vLLM server URL.
3. `requirements.txt` no longer uses `mineru[pipeline]` for MinerU parsing requirements.
4. `Dockerfile` no longer downloads `opendatalab/PDF-Extract-Kit-1.0`; it downloads `opendatalab/MinerU2.5-2509-1.2B` for MinerU.
5. Relevant settings/tests are updated and passing.
6. Operational flow (startup command/function path for server + MinerU client) is documented in project docs.
7. NoteLM is aligned to MinerU `3.0.7`, and the chosen integration path is validated against official MinerU scripts/functions.
8. The selected path is recorded with explicit runtime contract details for strict non-parallel server ownership, shutdown/VRAM-release handoff, ports, model naming, health checks, and timeout behavior.
9. The plan requires one shared `vllm_server.py` abstraction to manage both the MinerU parsing server role and the post-processing server role.
10. The selected path documents that the new external server is for MinerU parsing only while NoteLM keeps its own post-processing server lifecycle, with strict sequential handoff between them.
11. The selected path delegates parse-task concurrency to MinerU’s client/API server-side orchestration whenever feasible; if not feasible, the fallback includes explicit proof and an outer-parallelism constraint that avoids nested concurrency.
12. The plan explicitly covers settings/schema updates for backend, parse API routing, OpenAI `server_url`, `MINERU_MODEL_SOURCE`, and `MINERU_VL_MODEL_NAME`.
13. The plan explicitly removes or rejects legacy MinerU pipeline-era settings instead of preserving backward-compatibility shims.
14. The plan explicitly preserves or redefines the parse output artifact contract required by downstream NoteLM post-processing.
15. The plan explicitly states that the shared `vllm_server.py` abstraction owns only VLM-serving processes, while `mineru-api` lifecycle ownership is documented separately.
16. The plan records the actual served model identifier proof and the canonical removed-legacy-keys rejection contract.
