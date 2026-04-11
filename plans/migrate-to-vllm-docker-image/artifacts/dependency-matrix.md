# Task 01 Dependency Matrix

## Scope and Source-of-Truth Rules

- Primary source of truth: current working-tree repository files (`Dockerfile`, `requirements.txt`, `check_dependencies.py`, `handler.py`, `settings.py`, `vllm_worker.py`, `vllm_server.py`, `test/run.sh`, `README.md`).
- Explicitly excluded from dependency-usage proof: generated/copied build-context trees (for example `build/test/*`), as required by Task 01.
- Decision status legend:
  - `keep`: required by current supported runtime path.
  - `validate-before-keep`: likely needed, but must be revalidated against `vllm/vllm-openai:v0.18.0` baseline.
  - `validate-before-remove`: likely removable, but removal must be gated by proof in later tasks.
  - `remove`: safe to remove based on present evidence.

## Mandatory Proof Targets (Task 01 Requirement)

| Target | Source evidence | Runtime/CLI check | Recommendation | Confidence | Blocker if any |
| --- | --- | --- | --- | --- | --- |
| `paddlepaddle-gpu` | Explicit Docker install in `Dockerfile:97-99`; `paddle` import check in `check_dependencies.py:113` and import loop at `158-161`. | `python3 -c "import paddle"` via `check_dependencies.py`. | `validate-before-remove` | Medium | Current selected MinerU path is `vlm-http-client`, but hard removal proof under migrated base image is not yet executed. |
| `vllm` | Direct pin in `requirements.txt:10`; direct imports in `vllm_worker.py:36` and command construction `vllm serve` in `vllm_worker.py:809-836`; readiness checks in `vllm_server.py:84-131`; import and CLI checks in `check_dependencies.py:119`, `131-135`, `162-164`. | `python3 -c "import vllm"`, `python3 -c "import vllm.entrypoints.openai.api_server"`, `python3 -m mineru.cli.vlm_server openai_server --help`. | `keep` | High | None. |
| `cuda-bindings` | Direct pin in `requirements.txt:21`; module `cuda` import checked in `check_dependencies.py:127`. | `python3 -c "import cuda"` via `check_dependencies.py`. | `validate-before-keep` | Medium | Must confirm whether the new base image already satisfies the Python CUDA binding need without explicit pin drift. |
| `psutil` | Direct pin in `requirements.txt:2`; imported in `handler.py:26`; import check in `check_dependencies.py:107`. | `python3 -c "import psutil"` via `check_dependencies.py`. | `keep` | High | None. |
| `shapely` | Direct requirement in `requirements.txt:23`; import check in `check_dependencies.py:114`. | `python3 -c "import shapely"` via `check_dependencies.py`. | `validate-before-keep` | Medium | No direct NoteLM import found; likely MinerU/transitive requirement and must be proven by runtime smoke under new image. |
| `mineru[vllm]` extra package(s) | Requirement pin `requirements.txt:4`; package metadata for `mineru==3.0.7` resolves `extra == "vllm"` to `vllm>=0.10.1.1,<0.12` (PyPI metadata check during Task 01). | `python3 -m mineru.cli.vlm_server openai_server --help`, `mineru-openai-server --help` (`check_dependencies.py:133-138`). | `validate-before-keep` | High | Extra constraint range (`<0.12`) conflicts with direct `vllm==0.18.0` pin, so dependency strategy must be normalized in Task 03. |
| Docker apt packages/toolchain (`poppler-utils`, `libgl1`, `libglib2.0-0`, `curl`, `zstd`, `gcc`, `g++`, `python3-dev`, `gosu`) | Installed in `Dockerfile:85-94`. | No unified check today; current smoke is markdown existence in `test/run.sh:151-160`. | `validate-before-keep` (set-by-set below) | Medium | New base image may already include parts of this stack; must compare against migrated baseline before retaining all packages. |

## Python Dependency Matrix (`requirements.txt`)

| Package | Primary evidence in repo | Runtime role | Recommendation | Confidence | Notes |
| --- | --- | --- | --- | --- | --- |
| `uvloop==0.21.0` | `requirements.txt:1`; import check list in `check_dependencies.py:106`. | Event-loop performance dependency. | `validate-before-keep` | Medium | No direct import in NoteLM files found in Task 01 scan. |
| `psutil==5.9.0` | `requirements.txt:2`; `handler.py:26`; `check_dependencies.py:107`. | VRAM/process telemetry in handler path. | `keep` | High | Direct runtime import present. |
| `requests>=2.32.3,<3.0.0` | `requirements.txt:3`; `vllm_server.py:9`, used in readiness checks at `103-112`. | HTTP health/model readiness checks. | `keep` | High | Direct runtime usage. |
| `mineru[vllm]==3.0.7` | `requirements.txt:4`; MinerU subprocess and CLI path in `handler.py:505-518`, `548-565`; checks in `check_dependencies.py:109-112,131-152`. | Core OCR/parse orchestration path. | `keep` | High | Keep MinerU pin; normalize vLLM version interaction in Task 03. |
| `runpod==1.8.1` | `requirements.txt:5`; import check in `check_dependencies.py:115`; handler imports `runpod` in current code. | Serverless entrypoint integration. | `keep` | High | Required for deployment contract. |
| `httpx==0.28.1` | `requirements.txt:6`; imported in `vllm_worker.py:35`; check in `check_dependencies.py:117`. | Async retry/error-path handling for OpenAI-compatible calls. | `keep` | High | Direct runtime usage. |
| `huggingface_hub==0.36.2` | `requirements.txt:7`; `huggingface-cli download` in `Dockerfile:100`; direct import in `utils.py:31`. | Build-time model acquisition + runtime cache/model resolution helpers. | `keep` | High | Direct runtime import present. |
| `tiktoken==0.12.0` | `requirements.txt:8`; `vllm_worker.py:37` and token counting methods; check `check_dependencies.py:118`. | Chunk sizing/token budgeting. | `keep` | High | Direct runtime usage. |
| `langchain-text-splitters==0.3.11` | `requirements.txt:9`; `vllm_worker.py:38`. | Text chunking for post-processing. | `keep` | High | Direct runtime usage. |
| `vllm==0.18.0` | `requirements.txt:10`; `vllm_worker.py:809-836`; `vllm_server.py:84-131`; checks `check_dependencies.py:119,162-164`. | Local OpenAI-compatible serving for post-process + MinerU server path. | `keep` | High | Must remain version-deterministic with base image migration strategy. |
| `pydantic==2.12.5` | `requirements.txt:11`; `settings.py:12`; check `check_dependencies.py:120`. | Configuration validation models. | `keep` | High | Direct runtime usage. |
| `pydantic-settings==2.12.0` | `requirements.txt:12`; `settings.py:13`; check `check_dependencies.py:121`. | Env-driven settings loading. | `keep` | High | Direct runtime usage. |
| `json-repair==0.58.7` | `requirements.txt:13`; `vllm_worker.py:31`. | Robust JSON extraction/repair from model output. | `keep` | High | Direct runtime usage. |
| `transformers==4.57.6` | `requirements.txt:14`; direct imports in `utils.py:34`. | Tokenizer/config lookup for model-aware utilities. | `keep` | High | Direct runtime import present. |
| `numpy>=1.25,<2.3` | `requirements.txt:16`; import check `check_dependencies.py:124`. | Numeric backend dependency (direct/transitive). | `validate-before-keep` | Medium | No direct Task 01 import hit in NoteLM files. |
| `openai>=1.99.1,<2.0.0` | `requirements.txt:17`; `vllm_worker.py:36,40-46`; check `check_dependencies.py:116`. | API client for local vLLM OpenAI endpoint. | `keep` | High | Direct runtime usage. |
| `protobuf>=5.0,<7.0` | `requirements.txt:18`; `check_dependencies.py:125`. | Serialization/transitive runtime dependency. | `validate-before-keep` | Medium | Keep until migration smoke verifies safe reduction. |
| `starlette>=0.30.0,<1.0.0` | `requirements.txt:19`; `check_dependencies.py:123`. | API stack/transitive dependency. | `validate-before-keep` | Medium | No direct NoteLM import in Task 01 scan. |
| `filelock>=3.24.2,<4.0.0` | `requirements.txt:20`; `check_dependencies.py:126`. | Cache/model lock coordination (likely transitive). | `validate-before-keep` | Medium | Validate under migrated image. |
| `cuda-bindings==12.9.4` | `requirements.txt:21`; `check_dependencies.py:127`. | Python CUDA binding availability. | `validate-before-keep` | Medium | Must be validated against new base image Python/CUDA stack. |
| `langdetect==1.0.9` | `requirements.txt:22`; direct imports in `utils.py:32-33`. | Language detection for localized image markers. | `keep` | High | Runtime feature dependency. |
| `shapely>=2.0.7,<3.0.0` | `requirements.txt:23`; `check_dependencies.py:114`. | Likely MinerU geometry/transitive path. | `validate-before-keep` | Medium | No direct NoteLM import in Task 01 scan. |

## Dockerfile-Installed Dependencies Matrix

| Dependency/install step | Evidence | Runtime role hypothesis | Recommendation | Confidence | Gating proof required |
| --- | --- | --- | --- | --- | --- |
| `paddlepaddle-gpu==3.3.0` | `Dockerfile:97-99`; `check_dependencies.py:113`. | Legacy OCR/Paddle support path. | `validate-before-remove` | Medium | Must pass MinerU selected-path smoke + E2E without it on migrated base image. |
| `poppler-utils` | `Dockerfile:86`; not directly checked today. | PDF conversion/utilities often used by OCR pipelines. | `validate-before-keep` | Medium | Stage-4 smoke with representative PDFs. |
| `libgl1` | `Dockerfile:87`; `cv2` import checked in `check_dependencies.py:122`. | Native library for OpenCV-linked components. | `validate-before-keep` | Medium | Verify `cv2` import and runtime image operations on migrated image. |
| `libglib2.0-0` | `Dockerfile:88`; no direct check. | Common native dependency for image/GLib consumers. | `validate-before-keep` | Medium | Validate via `cv2` + MinerU parse flow. |
| `curl` | `Dockerfile:89`. | Build/debug utility only. | `validate-before-remove` | Medium | Keep only if needed by scripted validation/download in final flow. |
| `zstd` | `Dockerfile:90`. | Compression support (potentially transitive tooling). | `validate-before-keep` | Low | Needs explicit proof under migrated build. |
| `gcc`, `g++`, `python3-dev` | `Dockerfile:91-93`. | Build toolchain for pip wheels/native extensions. | `validate-before-remove` | Medium | Check whether migrated build still compiles anything from source. |
| `gosu` | `Dockerfile:94`; runtime subprocess call in `utils.py:101`. | Privilege/user write-access validation during ownership update path. | `validate-before-keep` | High | Needed when running ownership update path as root; validate if root path remains reachable in final runtime contract. |
| `pip install pip` bootstrap | `Dockerfile:95`. | Installer bootstrap/update step. | `validate-before-keep` | Medium | Might be redundant on vLLM base image; keep only if required for reproducible install behavior. |

## Check Ownership: `check_dependencies.py` vs Heavier Docker Smoke

- Keep in `check_dependencies.py` (fast module/CLI availability):
  - Python module importability checks (including `vllm`, `paddle`, `cuda`, MinerU modules).
  - CLI availability checks (`mineru-api`, `mineru-openai-server`, MinerU VLM CLI help).
  - Lightweight bounded served-model-name smoke (`check_dependencies.py:140-152`).
- Move/keep in Docker smoke workflow (heavier integration checks):
  - Actual server startup/readiness under container constraints.
  - MinerU parse + NoteLM post-process end-to-end sample run.
  - Output/data validation and persisted results artifacts.
  - Any proof needed for package/toolchain removal decisions.
