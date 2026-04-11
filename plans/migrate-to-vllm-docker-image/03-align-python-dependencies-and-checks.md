# Task 03 — Align Python Dependencies and Dependency Checks

## Dependencies
- Task 01 (`01-establish-baseline-and-dependency-matrix.md`)
- Task 02 (`02-migrate-dockerfile-to-vllm-base-image.md`)

## Requirements Traced
- FR-2 (dependency audit and cleanup)
- FR-3 (runtime validation coverage)
- FR-6 (aligned dependency checks/docs)
- NFR-1, NFR-3

## Implementation Steps

1. Update `requirements.txt` according to the dependency matrix:
   - keep direct NoteLM runtime dependencies that are still needed
   - remove packages proven unnecessary for the current Docker/runtime architecture
   - preserve explicit version pinning where the project depends on it
   - for every package removed from `requirements.txt` (or moved to Docker-only management), record one mandatory evidence pointer in the dependency-decision artifact (import/usage proof, CLI/runtime check result, or Docker validation result)
2. Reconcile `requirements.txt` with the new base image and Docker-installed packages so the same dependency is not managed in two conflicting places without purpose.
3. Reconcile dependency documentation with the Dockerfile-installed dependency decisions:
   - ensure packages removed from `requirements.txt` are not silently retained via Dockerfile installs without justification
   - ensure packages intentionally kept only in Dockerfile are documented as such in the dependency matrix
4. Update `check_dependencies.py` to reflect the new expected runtime contract:
   - remove checks for dependencies intentionally removed from the architecture
   - keep checks for required runtime imports/commands
   - separate lightweight availability checks from heavier Docker smoke validations
5. Align startup dependency-check behavior with the migrated Docker/runtime contract:
   - keep dependency checks out of Docker build stages
   - ensure runtime dependency checking is guarded by `DEBUG` (default `false`)
   - ensure `handler.py` startup runs the check only when `DEBUG=true`
6. Update any related documentation or comments that still describe the old dependency story.
7. If dependency removal is blocked by uncertain evidence, keep the dependency and record the blocker explicitly rather than removing it speculatively.

## Required Outputs/Artifacts

- `plans/migrate-to-vllm-docker-image/artifacts/dependency-decisions.md`
  - include one row per changed dependency with fields: `dependency`, `change`, `evidence-pointer`, `rationale`, `risk`, `owner/follow-up`

## Test Requirements
- Validate `python -m pip install -r requirements.txt` succeeds under the migrated Docker image strategy.
- Validate `check_dependencies.py` matches the new dependency set and produces actionable output.
- Validate dependency checks are triggered at runtime only when `DEBUG=true`, and are not part of Docker build-time validation steps.
- Validate removed dependencies are not still referenced by NoteLM source, Docker setup, or validation scripts.
- Validate that packages intentionally managed through Dockerfile rather than `requirements.txt` remain explicitly justified.
- Validate retained dependencies are still justified by direct usage or runtime proof.
- Validate every dependency removal/move decision has a non-empty evidence pointer in `dependency-decisions.md`.

## Execution Record (2026-04-11)

- `requirements.txt` cleanup was executed: it now retains only project-managed dependencies (`mineru`, `runpod`, `langchain-text-splitters`, `json-repair`, `langdetect`).
- `shapely` was removed from direct ownership because it is only declared by `mineru` as an optional `pipeline` extra and is not required by the current supported `vlm-http-client` runtime flow.
- Base-image-provided dependencies were removed from `requirements.txt` ownership and documented in `artifacts/dependency-decisions.md` with per-dependency rationale/risk/follow-up.
