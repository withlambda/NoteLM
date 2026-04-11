# Task 04 — Build the Single-Run Docker Validation Workflow

## Dependencies
- Task 01 (`01-establish-baseline-and-dependency-matrix.md`)
- Task 02 (`02-migrate-dockerfile-to-vllm-base-image.md`)
- Task 03 (`03-align-python-dependencies-and-checks.md`)

## Requirements Traced
- FR-3 (MinerU/vLLM/NoteLM validation)
- FR-4 (one image build + one container run)
- FR-5 (persisted results)
- FR-6 (docs alignment)
- NFR-2, NFR-3

## Implementation Steps

1. Refactor `test/run.sh` into the preferred top-level Docker validation entrypoint:
   - keep the current sample-data preparation and build-context behavior where still useful
   - remove interactive-only assumptions such as `-it` if they are no longer appropriate
2. Add a single in-container orchestration flow that runs sequential checks after one `docker run`:
   - dependency sanity / `check_dependencies.py` executed as a runtime stage (not during `docker build`)
   - MinerU and vLLM command or startup smoke checks
   - NoteLM handler end-to-end sample processing check
   - output verification for produced markdown artifacts
   - confirmation that required models/runtime assets are present for the supported path
   - include explicit debug-gated dependency stage behavior (`DEBUG=false` default, optional `DEBUG=true` run)
3. Mount one host-visible results location and make the validation flow write:
   - stage-by-stage pass/fail status
   - captured stdout/stderr or referenced log files
   - final summary suitable for local debugging
4. Standardize the persisted results schema:
   - `results/summary.json` containing stage list, per-stage status, timestamps, and final exit code
   - `results/stages/<stage-name>.log` (or one equivalent structured log file) for detailed diagnostics
   - stable stage identifiers (for example: `build`, `deps`, `cli-smoke`, `server-readiness`, `e2e-output`)
5. Ensure failures are recorded before the container exits non-zero.
   - trap/handler logic must flush `summary.json` and relevant logs to the mounted host path first, then return failure
   - if early-stage validation fails, still emit a complete summary with `skipped` statuses for remaining stages
6. Update `README.md` with the new Docker validation workflow if implementation changes how developers verify the image locally.
7. If `test/run.sh` becomes too dense, allow it to invoke one dedicated helper script, but keep the one-build/one-run contract and document the helper clearly.

## Required Outputs/Artifacts

- Host-mounted validation results directory containing, at minimum:
  - `summary.json`
  - stage-level logs (`stages/*.log` or one equivalently structured log artifact)
  - clear mapping from stage name to pass/fail/skipped

## Test Requirements
- Validate the Docker validation flow builds the image once.
- Validate all Docker-based checks run in one container lifecycle.
- Validate the workflow keeps dependency checks out of image build and executes them only in runtime validation stages.
- Validate the mounted results artifact is written on both success and failure paths.
- Validate the final workflow proves MinerU and vLLM function as intended for NoteLM’s current processing path.
- Validate the final workflow produces evidence for whether the remaining Dockerfile-installed dependencies and model downloads are truly required.
- Validate the workflow remains suitable for local review and iterative bug fixing.
- Validate result artifacts conform to the declared schema (`summary.json` + stage diagnostics) and include explicit status for every planned stage, including skipped stages after failures.
