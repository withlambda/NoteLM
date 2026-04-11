# Task 03 — Align Dependencies and Docker Model Scope to VLM-Only MinerU

## Dependencies
- Task 01 (`01-select-server-orchestration-path.md`)
- Task 02 (`02-refactor-runtime-to-vlm-http-client.md`)

## Requirements Traced
- FR-3 (remove pipeline dependency pressure)
- FR-4 (Docker downloads only MinerU VLM model for MinerU)
- NFR-3 (reproducible build)
- EC-4, EC-5

## Implementation Steps

1. Update Python package requirements:
   - Replace `mineru[pipeline]==...` with the exact minimal MinerU `3.0.7` requirement string selected in Task 01 for the chosen HTTP-client orchestration path.
   - Keep explicit version pins aligned with project compatibility policy.
   - Verify that the selected `3.0.7` install still exposes the official MinerU modules/scripts required by NoteLM (`mineru-api`, `mineru-openai-server`, or direct parse modules).
   - Record proof using the Task 01-selected validation method and exact commands/modules rather than a vague availability claim.
2. Produce a dependency/config matrix before touching Docker and validation scripts:
   - Requirement string/extras: exact MinerU `3.0.7` package spec and any companion packages that remain required.
   - Official modules/commands to prove: e.g. `mineru.cli.client`, `mineru.cli.fast_api`, `mineru.cli.vlm_server`, or the Task 01-selected direct-parse modules.
   - Runtime config/env keys: backend, local/remote parse API routing, OpenAI `server_url`, `MINERU_MODEL_SOURCE`, `MINERU_VL_MODEL_NAME`, the explicit MinerU-only external-server ownership split, and only the concurrency-related settings that remain valid after legacy setting removal.
   - Removed config/env keys: enumerate deprecated pipeline-era MinerU settings and job-input fields that are intentionally no longer supported, plus the canonical rejection mode used for them.
   - Model assets: explicitly keep `MinerU2.5-2509-1.2B` and explicitly remove `PDF-Extract-Kit-1.0` from the MinerU parsing path.
   - Served-model proof: record the observed served model identifier used by the selected path and how it maps to `MINERU_VL_MODEL_NAME`.
   - `check_dependencies.py` proof strategy: identify which items are verified by import, CLI `--help`, or subprocess smoke checks, and separate availability proof from one selected-path usability proof.
3. Update `Dockerfile` model download and config generation:
   - Remove `opendatalab/PDF-Extract-Kit-1.0` download step.
   - Keep `opendatalab/MinerU2.5-2509-1.2B` download step.
   - Ensure generated `mineru.json` stays valid for local model source and VLM path.
4. Review `check_dependencies.py` and related startup checks:
   - Remove/adjust pipeline-model assumptions.
   - Keep strict failure when required runtime dependencies are missing.
   - Add/adjust checks for MinerU `3.0.7` modules/scripts used by the chosen orchestration path.
   - Decide whether each proof should be an import check, CLI `--help` check, or subprocess smoke check, and keep the script aligned with that choice.
   - Do not keep dependency checks for removed legacy MinerU modes/settings.
5. Keep build non-interactive and deterministic:
   - No interactive download flows.
   - Preserve clear, pinned commands and explicit paths.
6. If Docker-based dependency validation is required for more than one check:
   - Prefer reusing the project `Dockerfile`; create a temporary validation Dockerfile only when extra validation-only tooling is required.
   - If such a Dockerfile is needed, place it under `plans/refactor-mineru-to-client-vllm-server-setup/validation/` alongside the orchestration assets.
   - Avoid per-test dependency downloads during container execution.
   - Mount one orchestration shell/Python script from `plans/refactor-mineru-to-client-vllm-server-setup/validation/` so all in-container dependency/build checks can run sequentially after one container start.
   - Mount a single results file path under `plans/refactor-mineru-to-client-vllm-server-setup/validation/` and require the orchestration script to append/store all validation outcomes there for extraction after the container stops.

## Test Requirements
- Validate `python -m pip install -r requirements.txt` succeeds with MinerU `3.0.7` and the selected extras.
- Validate official MinerU modules/scripts required by the chosen path are importable/invokable after install using the exact proof mechanism chosen in Task 01.
- Validate one bounded selected-path usability smoke check after install, separate from the availability checks above.
- Validate the dependency/config matrix stays consistent across `requirements.txt`, `check_dependencies.py`, Docker, runtime settings/docs, and the explicit split between MinerU parsing server ownership and NoteLM post-processing server ownership.
- Validate removed legacy settings no longer appear in runtime settings/docs/checks and that their documented rejection mode is consistent across artifacts.
- Validate Docker build script/commands no longer reference `PDF-Extract-Kit-1.0`.
- Validate Docker still downloads `MinerU2.5-2509-1.2B` and writes valid `mineru.json`.
- Validate dependency check script reflects the new expected runtime dependencies.
- If multiple of the above checks are run inside Docker, use one temporary validation image/container lifecycle for them rather than separate repeated downloads/executions.
- Capture all Docker-based dependency/build validation results in one mounted results file that can be reviewed outside the stopped container.
