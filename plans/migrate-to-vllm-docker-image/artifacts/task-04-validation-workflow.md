# Task 04 Docker Validation Workflow Record

Date: 2026-04-11

## Workflow Contract Implemented

- Canonical entrypoint remains `test/run.sh`.
- Exactly one Docker build per run:
  - `docker build -f Dockerfile -t notelm-migrate-validation .`
- Exactly one Docker container lifecycle per run:
  - `docker run --rm ... notelm-migrate-validation python3 -u docker_validation_workflow.py`
- Runtime dependency checks are executed only inside the container (`docker_validation_workflow.py` stage `deps`), not during image build.

## Stage IDs and Behavior

1. `debug-deps-default`
2. `deps`
3. `cli-smoke`
4. `server-readiness`
5. `e2e-output`
6. `runtime-assets`
7. `debug-deps-true` (optional; enabled via `VALIDATE_DEBUG_TRUE=1`)

Failure handling contract:

- On first failed stage, all remaining stages are recorded as `skipped` with explicit reason.
- `summary.json` is written before process exit.
- If the container exits before writing `summary.json`, `test/run.sh` writes a fallback summary on host.
- If image build fails, `test/run.sh` writes a build-failure summary with remaining stages marked `skipped`.

## Persisted Artifacts Schema

- Host-visible root: `build/test/results/`
- Required artifacts:
  - `summary.json`
  - `stages/<stage-id>.log`
- Additional diagnostics:
  - `output-manifest.json` (markdown output list from `e2e-output`)
  - `runtime-assets.json` (model/cache presence checks from `runtime-assets`)

## Notes for Follow-up Validation Runs

- Full integration proof for MinerU/vLLM/server readiness is container-runtime dependent and must be executed in a compatible Docker+GPU environment.
- Local macOS host constraints observed in prior tasks do not replace this Docker artifact contract.

## Local Runtime Sanity Evidence (2026-04-11)

- Image validated: locally rebuilt `notelm` (from current `Dockerfile` with removed explicit Paddle install and reduced apt list).
- Executed successfully in-container:
  - `python3 check_dependencies.py`
  - `python3 debug_dependencies.py` (default `DEBUG=false`)
  - `DEBUG=true python3 debug_dependencies.py`
  - `python3 -c "import handler; print('handler_import_ok')"`
- This confirms post-cleanup dependency/runtime startup sanity for the supported `vlm-http-client` path; full GPU readiness/e2e proof still follows the Task 04 one-build/one-run workflow in a compatible Docker+GPU environment.
