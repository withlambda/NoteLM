# Task 01 Model and Runtime Artifact Matrix

## Scope

- This matrix covers model/artifact assets explicitly installed/generated in the current `Dockerfile` and assets required by the supported NoteLM runtime path.
- Classification legend: `required`, `validate-before-keep`, `removable`.

## Model/Artifact Matrix

| Artifact | How it is produced today | Source evidence | Runtime consumer/path | Classification | Confidence | Notes / blocker |
| --- | --- | --- | --- | --- | --- | --- |
| MinerU VLM model `opendatalab/MinerU2.5-2509-1.2B` under `/app/models/mineru/vlm` | Downloaded in image build via `huggingface-cli download`. | `Dockerfile:100`; served-model-name smoke wiring in `check_dependencies.py:147-152`; MinerU server command wiring in `handler.py:516-517`. | MinerU parse server startup (`python -m mineru.cli.vlm_server ... --served-model-name ...`) and parse orchestration in handler. | `required` | High | Primary supported MinerU parse model for selected runtime path. |
| Generated MinerU config file `/app/mineru.json` | Built by inline Python in Docker build. | `Dockerfile:101`; environment variables pointing to this config in `Dockerfile:76-77`. | MinerU tools configuration resolution at runtime. | `required` | High | Must remain deterministic for container runtime behavior. |
| Hugging Face cache root (`XDG_CACHE_HOME=/app/cache`, `TORCH_HOME=/app/cache/torch`) | Set as environment defaults in image. | `Dockerfile:62-63`, cache dir creation in `Dockerfile:83`. | Model/runtime cache paths used by ML dependencies. | `validate-before-keep` | Medium | Keep unless migrated base image and runtime prove narrower scope is safe. |
| Local pre-bundled test/model trees mounted from host (`models/huggingface`, `models/datalab`) | Used by current local Docker smoke script through volume mounts (not image-baked in baseline Dockerfile). | `test/run.sh:118-121`. | Local test harness only; not authoritative proof for production image dependency needs. | `validate-before-keep` | Medium | Explicitly excluded as dependency-proof source per Task 01 scope rules. |
| Additional image-bundled model downloads beyond `MinerU2.5-2509-1.2B` | Not present in current baseline Dockerfile install steps. | `Dockerfile:100-101` (single explicit model download + config generation). | None currently evidenced for supported path. | `removable` | High | No extra explicit model download step exists in current Dockerfile baseline. |

## Required Runtime Assets for Supported Path

1. MinerU parse-side model identifier must stay aligned:
   - `MINERU_VL_MODEL_NAME` and `--served-model-name` wiring in handler startup path (`handler.py:505-518`).
2. MinerU runtime config path contract must remain valid:
   - `MINERU_TOOLS_CONFIG_JSON` / `MINERU_TOOLS_CONFIG_PATH` (`Dockerfile:76-77`) and generated file at `/app/mineru.json`.
3. NoteLM post-processing path relies on separate vLLM worker model settings:
   - VLLM serve command comes from `vllm_worker.py:809-836` and is independent from local test mount trees.

## Bloat Candidates to Re-Prove in Later Tasks

- Host-mounted cache/test model directories referenced by `test/run.sh` should not be used as proof that equivalent image-bundled assets are needed.
- Any future additional model downloads must provide explicit runtime evidence tuple before being accepted into migrated image.
