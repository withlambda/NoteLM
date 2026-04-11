# Task 02 — Refactor Runtime Wiring to MinerU `vlm-http-client`

## Dependencies
- Task 01 (`01-select-server-orchestration-path.md`)

## Requirements Traced
- FR-1 (MinerU parsing in HTTP-client mode)
- FR-2 (background server startup/readiness/lifecycle)
- FR-5 (explicit model routing)
- NFR-1, NFR-2
- EC-2, EC-3, EC-5

## Implementation Steps

1. Update settings schema in `settings.py`:
   - Add/confirm MinerU backend default for this flow (`vlm-http-client`).
   - Add/confirm MinerU parse API URL / local-API orchestration setting and validation if Option A is selected.
   - Add/confirm MinerU OpenAI `server_url` setting and validation.
   - Add/confirm `MINERU_MODEL_SOURCE` and optional MinerU model-name setting (`MINERU_VL_MODEL_NAME` mapping).
   - Remove deprecated MinerU settings and outer-concurrency controls (for example `mineru_workers`) that only belonged to the old NoteLM parse-pool contract, and reject them explicitly instead of keeping compatibility aliases.
   - Materialize the Task 01 canonical removed-legacy-keys list and one consistent rejection mode/layer for those keys.
2. Update MinerU settings extraction in `handler.py`:
   - Ensure job input overrides can set MinerU backend/API URL/OpenAI `server_url`/model source/model name safely.
   - Keep unknown-key behavior explicit.
   - Reject removed legacy MinerU keys explicitly instead of silently remapping them.
   - Apply the same canonical rejection contract chosen in Task 01 rather than ad hoc per-key behavior.
3. Refactor MinerU parse invocation path around the selected MinerU-native orchestration choice:
   - Preferred: reuse one `mineru-api` / `LocalAPIServer` orchestration entrypoint so NoteLM follows MinerU’s own parse-task flow end-to-end.
   - If Option A is selected, explicitly replace/bypass the current per-file multiprocessing parse flow in `handler.py` with the chosen shared-service orchestration contract; do not leave the old pool path in place unless Task 01 explicitly approves it.
   - For Option A, submit one input directory to the selected MinerU orchestration entrypoint; do not mirror its task submission internally and do not add a second NoteLM-owned concurrency layer around parse submission.
   - Treat MinerU’s client/API path server-side concurrency handling as the implementation target; do not keep NoteLM-owned active parse concurrency when Option A is selected.
   - Fallback: replace hardcoded `backend="pipeline"` with configured backend in direct parse calls and pass OpenAI `server_url` (`-u` equivalent argument path) for HTTP-client mode.
   - If a fallback direct-parse path is selected, constrain replacement outer parse parallelism to the Task 01-approved safe limit instead of preserving the existing pool behavior by default.
   - Ensure model-name env/config is set before parse execution when required.
   - Preserve or intentionally redefine the downstream parse output artifact contract from the current handler flow, including markdown-path discovery, image placement, and deterministic input-to-output mapping for post-processing.
4. Wire server lifecycle sequencing:
   - Start `mineru-openai-server` before MinerU parse and wait for `/health` readiness.
   - If Option A is selected, start/use local `mineru-api` only after the OpenAI-compatible server contract is ready.
   - Route both the MinerU parsing server role and the post-processing server role through one shared server-management class in `vllm_server.py`.
   - Keep `mineru-api` lifecycle management outside that shared manager boundary and follow the Task 01 decision for who owns it.
   - After MinerU parsing completes, stop/cleanup the parsing VLM server in all code paths (success and failure), wait for shutdown completion, run the Task 01 cleanup/cooldown steps, and enforce the Task 01 VRAM-release guardrail before any post-processing VLM server start is attempted.
   - Keep the existing post-processing flow isolated in runtime responsibility, with NoteLM retaining its own post-processing server path, but make it use the same `vllm_server.py` abstraction so both roles share lifecycle code without sharing a live process.
   - Encode the Task 01 server-ownership decision in code/config as strict sequential execution only; no parallel coexistence path is allowed.
5. Guardrails:
   - No silent fallback from HTTP-client mode to pipeline mode.
   - Fail fast with specific logs when server or model is unavailable.
   - Do not preserve the current multiprocessing pool or legacy compatibility shims if they conflict with MinerU’s supported shared-service concurrency model.
   - Ensure failure in OpenAI server startup, `mineru-api` startup, health readiness, shutdown completion, or VRAM-release handoff propagates clearly to the job result.

## Test Requirements
- Update existing MinerU settings extraction tests for backend, API URL, OpenAI `server_url`, `MINERU_MODEL_SOURCE`, model name, and explicit rejection/removal of deprecated legacy-concurrency settings.
- Add new handler orchestration tests verifying the selected MinerU-native path is used, that `vlm-http-client` receives the correct OpenAI `server_url`, and that NoteLM does not retain an outer parse-concurrency layer when Option A is selected because MinerU-side concurrency remains preferred.
- Verify failure-path behavior when either `mineru-api` or `mineru-openai-server` startup/readiness fails.
- Verify handler control flow does not silently fall back to `pipeline`.
- Verify the MinerU parsing VLM server is stopped and the VRAM-release handoff is satisfied before NoteLM’s own post-processing VLM server is started.
- Verify parse-phase failure after startup still triggers cleanup of the parsing server and blocks post-processing startup unless the selected contract explicitly says otherwise.
- Verify both VLM-serving roles are started through the shared `vllm_server.py` manager rather than through separate process-management code paths, while `mineru-api` lifecycle remains outside that manager boundary.
- Verify the downstream parse output artifact contract remains valid for post-processing or is intentionally redefined and documented as approved in Task 01.
- Verify removed legacy keys fail through the same canonical rejection contract in both settings parsing and job-input handling.
