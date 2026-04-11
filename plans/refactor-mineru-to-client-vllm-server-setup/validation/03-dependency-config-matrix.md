# Task 03 Dependency / Config Matrix

## 1) Requirement String and Companion Packages

- `requirements.txt` uses `mineru[vllm]==3.0.7` (selected Task 01 path).
- Companion runtime packages remain pinned in `requirements.txt`, including `vllm==0.18.0` and related API/runtime packages used by NoteLM.

## 2) Official MinerU Modules / Commands and Proof Strategy

| Item | Proof Type | Validation Command |
| --- | --- | --- |
| `mineru.cli.client` | import + CLI `--help` | `python3 -c "import mineru.cli.client"`, `python3 -m mineru.cli.client --help` |
| `mineru.cli.fast_api` | import | `python3 -c "import mineru.cli.fast_api"` |
| `mineru.cli.vlm_server` | import + CLI `--help` | `python3 -c "import mineru.cli.vlm_server"`, `python3 -m mineru.cli.vlm_server openai_server --help` |
| `mineru-api` | CLI `--help` | `mineru-api --help` |
| `mineru-openai-server` | CLI `--help` | `mineru-openai-server --help` |
| Selected-path bounded usability | subprocess smoke | `python3 -m mineru.cli.vlm_server openai_server --served-model-name opendatalab/MinerU2.5-2509-1.2B --help` |

These checks are encoded in `check_dependencies.py`.

## 3) Runtime Keys: Keep vs Remove

### Keep (runtime contract)

- Backend/routing: `MINERU_BACKEND`, `MINERU_API_URL`, `MINERU_SERVER_URL`
- Model source / identifier: `MINERU_MODEL_SOURCE`, `MINERU_VL_MODEL_NAME`
- MinerU server lifecycle/concurrency-related keys that remain valid in current runtime:
  - `MINERU_VLM_HOST`, `MINERU_VLM_PORT`, `MINERU_VLM_MODEL_PATH`
  - `MINERU_VLM_STARTUP_TIMEOUT`, `MINERU_VLM_HEALTH_CHECK_INTERVAL`
  - `MINERU_VLM_SHUTDOWN_GRACE_PERIOD`, `MINERU_VLM_COOLDOWN_SECONDS`

### Removed legacy keys (explicit rejection mode)

- Removed keys: `MINERU_WORKERS`, `MINERU_VRAM_GB_PER_WORKER`, `MINERU_DISABLE_MAXTASKSPERCHILD`, `MINERU_MAXTASKSPERCHILD` and lowercase/job-input aliases.
- Canonical rejection mode: `ValueError` raised via `reject_removed_mineru_legacy_keys` in `settings.py`.

## 4) Model Asset Scope

- Keep: `opendatalab/MinerU2.5-2509-1.2B`.
- Remove from MinerU parsing path: `opendatalab/PDF-Extract-Kit-1.0`.
- Docker `mineru.json` generation now writes VLM-only model-dir mapping:
  - `{ "models-dir": { "vlm": "/app/models/mineru/vlm" }, "config_version": "1.3.1" }`

## 5) Served-Model Mapping Evidence

- Selected served-model identifier: `opendatalab/MinerU2.5-2509-1.2B`.
- Mapping target: `MINERU_VL_MODEL_NAME` default/value in `settings.py` aligns to the same identifier.

## 6) Ownership Split Consistency

- MinerU parsing server ownership remains under MinerU-side server/client route settings (`MINERU_BACKEND`, MinerU URLs/ports).
- NoteLM post-processing OpenAI ownership remains separate in its own OpenAI/runtime settings and is not merged into removed MinerU legacy worker knobs.
