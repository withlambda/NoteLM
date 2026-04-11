# Task 04 — Validate and Document the MinerU Server/Client Flow

## Dependencies
- Task 02 (`02-refactor-runtime-to-vlm-http-client.md`)
- Task 03 (`03-align-dependencies-and-docker-model-scope.md`)

## Requirements Traced
- FR-1, FR-2, FR-4, FR-5, FR-6
- NFR-1, NFR-4
- Definition of Done items 1–16

## Implementation Steps

1. Extend and run tests:
   - Update existing MinerU settings extraction tests to include backend/API URL/OpenAI `server_url`/`MINERU_MODEL_SOURCE`/model-name assertions and explicit rejection of removed legacy MinerU keys.
   - Add new handler-orchestration tests to verify ordering: OpenAI server start → health-ready → local `mineru-api` start (if used) → MinerU parse call.
   - Add new handler-orchestration tests to verify NoteLM delegates parse-task concurrency to MinerU’s client/API server-side handling when that path is selected, or else enforces the documented fallback concurrency cap.
   - Add new handler-orchestration tests to verify failure propagation and explicit absence of fallback to `pipeline`.
   - Add new output-contract tests to verify the post-parse markdown/image artifact layout still matches downstream post-processing expectations, or that any intentional change is explicitly documented and consumed correctly.
   - Add new lifecycle-cleanup tests to verify the strict handoff rule: MinerU parsing VLM server stop → shutdown completion / VRAM-release guardrail → NoteLM post-processing VLM server start.
   - Add new lifecycle-cleanup tests to verify parse-phase failure after startup still shuts down the parsing VLM server and blocks post-processing startup unless the selected contract explicitly allows otherwise.
   - Add/extend shared manager tests to verify MinerU parsing uses the external server path, NoteLM retains its own post-processing server path, and both phases are started through the same shared `vllm_server.py` manager abstraction.
   - Add/extend manager-boundary tests to verify the shared `vllm_server.py` abstraction owns only VLM-serving processes and does not silently absorb `mineru-api` lifecycle management.
   - Add/extend configuration tests to verify the canonical removed-legacy-keys list and rejection mode stay identical across settings parsing and job-input handling.
2. Perform focused runtime validation:
   - Run targeted checks that the configured local API URL and OpenAI `server_url` are used in the correct roles.
   - Verify failure behavior for bad URL/unready server remains explicit and actionable.
   - Run a container-level or subprocess-level smoke check using the official MinerU `3.0.7` scripts/functions selected by the plan.
   - Keep the smoke check bounded and deterministic: one representative sample run with captured readiness evidence and without broad exploratory load.
   - If several runtime validations need the same Docker environment, prefer reusing the project `Dockerfile`; if extra validation-only tooling is required, prepare one temporary validation Dockerfile/image under `plans/refactor-mineru-to-client-vllm-server-setup/validation/` and execute the in-container checks sequentially through one mounted orchestration shell/Python script during a single container start.
   - Mount one results file path under `plans/refactor-mineru-to-client-vllm-server-setup/validation/` for the orchestration script so readiness evidence, command outcomes, and smoke-check results can be extracted after container shutdown.
3. Update operational documentation (`README.md`):
   - Document required env vars and defaults (`MINERU_MODEL_SOURCE`, `MINERU_VL_MODEL_NAME`, parse API host/port, OpenAI server host/port).
   - Document the selected MinerU-native startup sequence and troubleshooting hints.
   - Document the MinerU `3.0.7` version alignment decision.
   - Document that MinerU parsing uses the external MinerU-facing server path, NoteLM post-processing keeps its own server lifecycle, both phases are strictly sequential, the parse server must stop before post-processing server startup, and how the shared `vllm_server.py` manager enforces that handoff.
   - Document who owns parse-task concurrency, which legacy MinerU settings were removed as part of the breaking refactor, the canonical rejection mode for those removed keys, and why nested parallelism is intentionally avoided in favor of MinerU-side server/API concurrency handling.
   - Document the selected served-model identifier contract and how it maps to `MINERU_VL_MODEL_NAME`.
4. Final consistency pass:
   - Ensure no stale instructions continue to imply MinerU pipeline-model requirement for this flow.
   - Ensure docs align with actual implementation path selected in Task 01.
   - Ensure docs distinguish `mineru-api` orchestration from `mineru-openai-server` model serving when both are used.
   - Ensure docs distinguish the MinerU external parsing-server lifecycle from NoteLM’s retained post-processing server lifecycle.
   - Ensure docs/tests agree that the shared `vllm_server.py` manager owns only VLM-serving processes, not `mineru-api`.
   - Ensure docs no longer imply `PDF-Extract-Kit-1.0` is required for MinerU parsing.
   - Ensure the final docs, tests, and validation notes all agree on the exact parse-concurrency owner, fallback behavior, parse output artifact contract, served-model identifier proof, and legacy-key rejection behavior.

## Test Requirements
- Run all updated/added tests relevant to MinerU settings extraction and handler invocation flow.
- Record evidence that service readiness is checked before MinerU requests.
- Verify docs match the implemented MinerU `3.0.7` command/function flow and do not reference removed `PDF-Extract-Kit-1.0` requirement for MinerU parsing.
- Verify docs and tests both state that removed legacy MinerU settings are no longer supported.
- Record evidence that the strict non-parallel server-ownership rule, the MinerU-only external parsing server decision, the retained NoteLM post-processing server decision, the shutdown/VRAM-release handoff, the shared `vllm_server.py` manager path for VLM-serving processes only, the dependency-proof method, the selected parse-concurrency owner, the parse output artifact contract, the served-model identifier proof, and the legacy-key rejection contract were all executed as planned.
- If multiple runtime validations are containerized, execute them economically within one prepared validation container run instead of repeatedly rebuilding/downloading the same dependencies.
- Store all containerized validation evidence in one mounted results file produced by the orchestration script and review that file outside the container.
