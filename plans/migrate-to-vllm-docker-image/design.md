# Design — Docker Migration to `vllm/vllm-openai:v0.18.0`

## Task Execution Order

```text
Task 01 (Baseline + Dependency Matrix)
  └─→ Task 02 (Dockerfile Migration to vLLM Base Image)
        └─→ Task 03 (Requirements + Dependency Check Alignment)
              └─→ Task 04 (Single-Run Docker Validation Harness + Documentation)
```

Task 01 is the decision gate for the rest of the plan because it determines which current dependencies are still justified once the base image changes.

## Current Baseline (Task 01 Snapshot Before Migration)

### Current Dockerfile Behavior
- `Dockerfile` currently uses a `pytorch/pytorch` CUDA runtime base image selected through build args.
- It installs system packages such as `poppler-utils`, `libgl1`, `libglib2.0-0`, `curl`, `zstd`, `gcc`, `g++`, `python3-dev`, and `gosu`.
- It explicitly installs `paddlepaddle-gpu==3.3.0` from the CUDA 12.6 index before installing `requirements.txt`.
- It then installs pinned Python requirements, downloads `opendatalab/MinerU2.5-2509-1.2B`, generates `/app/mineru.json`, runs `check_dependencies.py`, and creates `appuser`.
- The current image therefore has three independent footprint categories that must be revalidated: OS/toolchain packages, explicit Python installs, and model artifacts downloaded into the image.

### Current Dependency Baseline
- `requirements.txt` currently includes a mix of direct NoteLM/runtime packages and infrastructure-facing packages such as `mineru[vllm]==3.0.7`, `vllm==0.18.0`, `cuda-bindings==12.9.4`, `psutil`, and `shapely`.
- Prior analysis already established two important constraints:
  1. `vllm/vllm-openai:v0.18.0` is a realistic new base-image candidate and already carries CUDA-oriented runtime/tooling.
  2. Upstream MinerU’s current `vlm-http-client` path does not by itself prove the need for a local Paddle install.

### Current Docker Validation Harness
- `test/run.sh` currently prepares `build/test`, copies a partial build context, installs setup requirements, generates sample PDFs, builds the Docker image once, runs one container, and finally checks only whether markdown output files exist.
- The current script is useful as a starting point, but it does not yet persist a structured validation report and it still relies on an interactive `docker run -it` flow.

## Target Design

## 1. Dependency-Audit-First Migration

Before changing runtime packages, the migration should produce a dependency matrix that maps each current dependency to one of the following sources of necessity:

- direct NoteLM imports
- runtime subprocess/CLI requirements
- transitive requirements that still need explicit pinning
- packages already satisfied by the new base image
- legacy carryovers that can be removed after proof
- required model artifacts versus redundant image-bundled assets

The dependency matrix should cover at least:

- `requirements.txt`
- explicit Docker-installed Python packages (`paddlepaddle-gpu` today)
- Docker-installed OS/build packages from `apt-get install`
- Docker-bundled model downloads and generated runtime config artifacts
- `check_dependencies.py`
- runtime entrypoints that shell out to MinerU or vLLM commands

This prevents migrating the base image while accidentally preserving obsolete installs from the old PyTorch-based container.

## 2. Dockerfile Migration Strategy

### Target State
- Change `Dockerfile` to start from `vllm/vllm-openai:v0.18.0`.
- Keep NoteLM-specific environment variables, copied application files, model download steps, dependency checks, and non-root user creation.
- Revalidate which system packages are still needed on top of the new base image.
- Reduce the image so it retains only the models and Docker-installed dependencies that the supported NoteLM runtime path actually needs.
- Revalidate whether `pip install -r requirements.txt` should retain `vllm==0.18.0` as an explicit pin, rely on the base image copy, or deliberately reinstall to keep the Python environment deterministic.

### Migration Rules
- Do not assume packages from the old image are missing from the new image; inspect and document the new baseline.
- Do not keep explicit Python installs only because they were previously required on the PyTorch base.
- Do not keep apt packages, build tools, or model downloads only because they existed in the legacy Dockerfile; require current-runtime proof.
- Preserve deterministic model setup for MinerU (`MinerU2.5-2509-1.2B` and generated `mineru.json`).

## 3. Validation Harness Architecture

### Preferred Entry Point
- Keep `test/run.sh` as the top-level local command that developers execute.
- Refactor it to run non-interactively and to invoke one in-container validation orchestrator.

### In-Container Validation Flow

```text
docker build (once)
  └─ docker run (once)
       └─ mounted validation orchestrator executes sequential checks:
            1. environment + dependency sanity checks
            2. MinerU/vLLM CLI availability checks
            3. server readiness / startup smoke checks
            4. NoteLM handler end-to-end sample processing
            5. output verification + results summary writeout
```

### Result Persistence
- Mount one host-visible results path, for example under `build/test/results/`.
- Write a consolidated summary file plus detailed logs for each stage, or one structured log file with clear stage boundaries.
- Ensure the orchestration layer traps failures, records them to the mounted results path, and only then exits non-zero.

## 4. Validation Scope

The migrated harness should validate four levels of confidence, in order:

1. **Build confidence**
   - Docker image builds successfully from the migrated `Dockerfile`.
2. **Dependency/runtime confidence**
   - `check_dependencies.py` matches the new expected environment.
   - Required MinerU/vLLM commands and modules remain available.
3. **Service confidence**
   - The vLLM-serving path used by NoteLM/MinerU starts and reaches readiness under the new image assumptions.
4. **End-to-end workflow confidence**
   - The container processes sample PDFs through the NoteLM flow and produces markdown output.

## 5. Affected Files

### Likely Modified During Implementation
- `Dockerfile`
- `requirements.txt`
- `check_dependencies.py`
- `test/run.sh`
- `README.md`

### Likely Added During Implementation
- A Docker validation orchestrator script under `test/` or another clearly documented project path if `test/run.sh` alone becomes too complex.
- A mounted results-file convention or results directory layout for Docker validation output.

## 6. Dependency and Interface Changes to Capture

### Dependency-Level Decisions
- Whether `paddlepaddle-gpu` is removed from the Docker build.
- Whether `vllm==0.18.0` stays pinned in `requirements.txt`, is deliberately reinstalled on top of the base image, or is handled another documented way.
- Whether packages such as `cuda-bindings`, `psutil`, and `shapely` remain direct requirements or move out of the explicit dependency set.
- Which apt-installed OS/build packages remain justified once the base image changes.
- Which model artifacts are truly required in the final image and which can be removed from the Docker build path.

### Tooling/Workflow Changes
- `test/run.sh` should stop depending on an interactive terminal.
- The Docker validation flow should expose a stable host path for results review.
- The validation contract should define whether failures abort immediately or continue long enough to capture all planned evidence; whichever rule is chosen must still guarantee useful logs.

## 7. Open Questions to Resolve During Execution

1. Does the new vLLM base image already provide enough of the Python/runtime stack to simplify `requirements.txt` or Docker installs without losing determinism?
2. Which Dockerfile-installed apt packages or build tools are still required after the base-image migration?
3. Is `paddlepaddle-gpu` truly removable for the current NoteLM + MinerU `vlm-http-client` flow in this repository?
4. Which model downloads must remain in the image for the supported runtime path, and are any currently redundant?
5. Which checks belong in `check_dependencies.py` versus the Docker validation harness?
6. Is it sufficient to keep all validation logic in `test/run.sh`, or is a small mounted in-container helper script needed to keep the flow readable and failure-safe?

The implementation tasks below are ordered to answer those questions before irreversible cleanup happens.

## 8. Execution Status Note (2026-04-11)

- Task 02 Docker cleanup has been executed and validated on the locally rebuilt `notelm` image.
- Explicit `paddlepaddle-gpu==3.3.0` installation was removed from `Dockerfile`; current runtime checks pass without it for the supported `vlm-http-client` path.
- Legacy apt package installs (`poppler-utils`, `libglib2.0-0`, `curl`, `zstd`, `gcc`, `g++`, `python3-dev`, `gosu`) were removed; only currently justified apt packages remain (`fonts-noto-core`, `fonts-noto-cjk`, `fontconfig`, `libgl1`).
- Task 03 dependency cleanup has been executed and recorded.
- `requirements.txt` was reduced to project-managed dependencies only; base-image-provided dependencies were removed from direct ownership.
- Cleanup evidence and per-dependency rationale/risk/follow-up are captured in `plans/migrate-to-vllm-docker-image/artifacts/dependency-decisions.md`.
