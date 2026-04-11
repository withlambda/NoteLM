# Task 02 — Migrate `Dockerfile` to the vLLM OpenAI Base Image

## Dependencies
- Task 01 (`01-establish-baseline-and-dependency-matrix.md`)

## Requirements Traced
- FR-1 (base-image migration)
- FR-3 (MinerU/vLLM behavior preserved)
- FR-6 (supporting docs/checks alignment)
- NFR-1, NFR-3, NFR-4

## Implementation Steps

1. Replace the old PyTorch CUDA runtime base-image strategy with `vllm/vllm-openai:v0.18.0`.
2. Reconcile Dockerfile setup steps against the new base image:
   - keep only the apt packages still needed by NoteLM
   - verify compiler/tooling needs for any Python packages still installed from source wheels
   - preserve NoteLM environment variables and working-directory layout
3. Revisit explicit Python installs performed before `requirements.txt`:
   - remove legacy explicit installs that the dependency matrix proves unnecessary
   - retain only the installs that remain justified and document why
4. Preserve deterministic MinerU model setup:
   - keep the `MinerU2.5-2509-1.2B` download only if it is still required for the supported runtime path
   - remove or avoid model downloads that the matrix proves unnecessary
   - keep `mineru.json` generation aligned with NoteLM runtime expectations
5. Ensure dependency checks are runtime-gated instead of build-gated:
   - do not execute `check_dependencies.py` (or `debug_dependencies.py`) during `docker build`
   - define image env default `DEBUG=false`
   - keep runtime startup wired so dependency checks can run before handler startup only when `DEBUG=true`
6. Ensure the container still creates and uses the intended non-root runtime user if that remains part of the deployment contract.

## Test Requirements
- Validate that the migrated Dockerfile builds successfully.
- Validate that the image still contains the OS/runtime pieces NoteLM needs for MinerU, vLLM, and document conversion flow, and no unproven Dockerfile-installed dependency is kept without justification.
- Validate that the image includes the required models/runtime artifacts for the supported flow and does not keep extra model downloads without documented need.
- Validate that the migrated image continues to reach the same application startup path (`handler.py` by default) or the intentionally updated equivalent.
- Validate that no Dockerfile step still depends on the removed PyTorch-base assumptions.
- Validate that Docker build does not run dependency checks and that runtime debug-gated checks are controlled via `DEBUG` (default `false`).

## Execution Record (2026-04-11)

- `Dockerfile` migration to `vllm/vllm-openai:v0.18.0` is in place and locally rebuilt as image tag `notelm`.
- Explicit `paddlepaddle-gpu==3.3.0` installation was removed.
- Removed legacy apt/toolchain installs: `poppler-utils`, `libglib2.0-0`, `curl`, `zstd`, `gcc`, `g++`, `python3-dev`, `gosu`.
- Retained apt installs with current proof path: `fonts-noto-core`, `fonts-noto-cjk`, `fontconfig`, `libgl1`.
- Runtime sanity evidence on `notelm`: `check_dependencies.py` passes, `debug_dependencies.py` runs for both default and `DEBUG=true`, and `import handler` succeeds.
