# Refactor MinerU to Client vLLM Server Setup — IMPLEMENTED

## Implementation Summary

- Executed Task `04-validate-and-document-server-client-flow` by validating the selected MinerU `vlm-http-client` parse path and documenting server/client lifecycle ownership, role separation, and failure behavior.
- Expanded orchestration and settings extraction tests to enforce:
  - parse API URL vs OpenAI `server_url` role wiring,
  - `MINERU_MODEL_SOURCE` / `MINERU_VL_MODEL_NAME` propagation,
  - strict parse lifecycle stop/handoff behavior,
  - explicit no-fallback rejection of non-supported backend values,
  - deterministic parse artifact normalization expectations.
- Added Task 04 validation evidence artifact with deterministic test outputs, bounded subprocess smoke checks, explicit unready-endpoint timeout behavior, and host limitation notes for the current macOS environment's incomplete dependency set.
- Synchronized `README.md` with the current MinerU server/client flow, removed stale worker-era operational guidance, and documented legacy-key rejection behavior.

## New / Modified Files

- Modified: `README.md`
- Modified: `test/test_handler_settings_extraction.py`
- Added: `test/test_handler_orchestration.py`
- Added: `plans/refactor-mineru-to-client-vllm-server-setup/validation/04-server-client-flow-validation.md`

## Validation and Test Execution

- Targeted orchestration flow checks:
  - `python3 -m pytest -q test/test_handler_orchestration.py::TestHandlerOrchestration::test_handler_uses_orchestrated_vlm_http_client_path test/test_handler_orchestration.py::TestHandlerOrchestration::test_parse_failure_stops_parse_server_and_blocks_postprocess`
- Task-level suite:
  - `python3 -m pytest -q test/test_handler_orchestration.py test/test_handler_settings_extraction.py test/test_settings.py`
- Full project suite (final-task requirement):
  - `python3 -m pytest` → `87 passed`
- Bounded runtime smoke checks:
  - MinerU CLI invocation path checks (`mineru.cli.client`, `mineru.cli.vlm_server`, served-model-name wiring)
  - Explicit unready server check via `VllmServerManager` resulting in deterministic `TimeoutError`.

## Deviations and Rationale

- Full dependency validation in this macOS host remains constrained because the current local environment is missing some required packages from `requirements.txt` (`psutil`, `shapely`) and also lacks Linux/GPU stack packages (`vllm`, `paddle`, `cuda`, etc.); Task 04 artifacts therefore document successful bounded command/test evidence plus explicit host limitation details rather than a fully green `check_dependencies.py` result on this host.
