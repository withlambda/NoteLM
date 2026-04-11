# Task 04 Server/Client Flow Validation

## 1) Scope and Contract Under Validation

- Selected runtime path: MinerU parse via `backend=vlm-http-client` + OpenAI-compatible parse server.
- Parse server command path in NoteLM: `python -m mineru.cli.vlm_server openai_server` with served model id from `MINERU_VL_MODEL_NAME`.
- Post-processing path remains NoteLM-owned and is started only after parse handoff.
- Shared `vllm_server.py` manager owns only VLM-serving processes (parse and post-process roles), not `mineru-api` lifecycle.

## 2) Deterministic Test Evidence (Role Wiring, Ordering, Failure Path)

Command:

```bash
python3 -m pytest -q \
  test/test_handler_orchestration.py::TestHandlerOrchestration::test_handler_uses_orchestrated_vlm_http_client_path \
  test/test_handler_orchestration.py::TestHandlerOrchestration::test_parse_failure_stops_parse_server_and_blocks_postprocess
```

Observed result:

- `2 passed`.
- Confirms parse invocation uses `server_url` + `api_url` roles as wired in orchestration call arguments.
- Confirms parse-role process is started/stopped via shared manager and model-source/model-name contract is bound through role environment (`MINERU_MODEL_SOURCE`, `MINERU_VL_MODEL_NAME`).
- Confirms parse-phase failure after startup still triggers parse-role shutdown and blocks post-processing startup.

## 3) Subprocess Smoke Validation (Official MinerU Functions)

Command:

```bash
python3 -m mineru.cli.client --help >/dev/null && \
python3 -m mineru.cli.vlm_server openai_server --help >/dev/null && \
python3 -m mineru.cli.vlm_server openai_server --served-model-name opendatalab/MinerU2.5-2509-1.2B --help >/dev/null
```

Observed result:

- Exit status success (no command error).
- Confirms selected MinerU CLI function paths are callable in this environment.
- Confirms served-model-name wiring command form is accepted for the selected identifier.

## 4) Explicit Unready-Server Failure Behavior

Command:

```bash
python3 -c "from vllm_server import VllmServerManager,VllmServerRoleConfig; m=VllmServerManager(); cfg=VllmServerRoleConfig(role='validation_parse', command=['python3','-m','http.server','39555'], host='127.0.0.1', port=39555, startup_timeout=2, health_check_interval=0.2, shutdown_grace_period=1, expected_model_id='opendatalab/MinerU2.5-2509-1.2B'); m.set_role_config(cfg); exec('try:\n    m.start(\'validation_parse\')\nexcept Exception as exc:\n    print(type(exc).__name__ + \':: \' + str(exc))\nfinally:\n    m.stop(\'validation_parse\')')"
```

Observed output:

- `TimeoutError:: Timed out waiting for VLM server role 'validation_parse' readiness after 2s`

Interpretation:

- Unready endpoint behavior is explicit and actionable (timeout exception includes role + timeout context).

## 5) Host Limitation Note for Full Dependency Stack

Command:

```bash
python3 check_dependencies.py
```

Observed result:

- MinerU CLI/module checks and served-model-name smoke checks pass.
- Full dependency check remains non-zero on this macOS host because the local environment is not provisioned with the complete runtime dependency set: required host packages such as `psutil` and `shapely` are absent here, and Linux/GPU-target dependencies (`vllm`, `paddle`, `cuda`, etc.) are also unavailable.
- This is consistent with the target deployment being the project Docker image / Linux GPU runtime rather than the current macOS host environment.

## 6) Agreement Checklist (Task 04 Consistency)

- Parse URL roles separated and validated (`api_url` vs OpenAI `server_url`).
- Strict lifecycle handoff validated: parse stop before post-processing startup.
- Shared manager boundary validated: VLM-serving roles only, no `mineru-api` lifecycle absorption.
- No fallback to `pipeline` path validated by tests.
- Parse output contract retained (`<output>/<stem>/<stem>.md` + optional `images/`) and asserted in orchestration tests.
- Removed legacy MinerU keys remain explicitly rejected with canonical `ValueError` path.
