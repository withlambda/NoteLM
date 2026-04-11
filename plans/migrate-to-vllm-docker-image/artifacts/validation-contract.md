# Task 01 Future Docker Validation Contract

## Objective

Define the migration-time validation workflow so later tasks can prove correctness with **one image build**, **one container run**, **sequential checks**, **non-interactive execution**, and **persisted host-visible results**.

## Contract Decisions

### 1) Build/Run Cardinality

- Build exactly once per validation session:
  - `docker build -f Dockerfile -t notelm-migrate-validation .`
- Run exactly once per validation session:
  - `docker run --rm ... notelm-migrate-validation`
- Multi-run fallback is allowed only for explicit debug mode and must not replace the required single-run evidence path.

### 2) Non-Interactive Execution

- `docker run` must not use `-it`.
- Any helper commands used by the validation path must be non-interactive and deterministic.
- Current baseline issue: `test/run.sh` currently appends `-it` (`test/run.sh:122`), which must be removed in Task 04.

### 3) Sequential In-Container Checks (Single Run)

The single container run executes these stages in order:

1. **Environment + dependency sanity**
   - Run `python3 check_dependencies.py` (or equivalent staged checks).
2. **MinerU/vLLM CLI availability**
   - Verify `mineru-api`, `mineru-openai-server`, and `python3 -m mineru.cli.vlm_server openai_server --help`.
3. **Server startup/readiness smoke**
   - Validate that the MinerU/vLLM serving path reaches readiness (not only importability).
4. **NoteLM end-to-end sample processing**
   - Execute handler workflow with sample inputs through parse + optional post-process path.
5. **Output + summary emission**
   - Verify output artifacts and write a machine-readable summary.

### 4) Persisted Results Contract

- Mount one host-visible results directory, e.g. `build/test/results/`.
- Persist at minimum:
  - `summary.json` (stage statuses, pass/fail, durations, exit code)
  - `stage-logs/*.log` (or one structured combined log with stage boundaries)
  - output verification manifest (list of generated markdown paths)
- Failure behavior: each stage logs failure context before final non-zero exit.

### 5) Orchestration Surface Decision (`test/run.sh` vs helper)

- **Decision**: keep `test/run.sh` as top-level launcher, but delegate in-container sequencing to one dedicated helper script.
- Rationale:
  - Current `test/run.sh` already performs setup, copy, build, run, and output checks (`test/run.sh:45-160`).
  - Adding full staged orchestration + structured result persistence there would reduce readability and increase fragility.
  - A dedicated in-container helper keeps `test/run.sh` concise while preserving one-build/one-run requirements.

### 6) Responsibility Split: `check_dependencies.py` vs Docker smoke

- `check_dependencies.py` remains fast/static availability gate:
  - imports, CLI `--help`, bounded served-model-name argument wiring checks.
- Docker smoke remains heavy integration gate:
  - startup/readiness, full parse + postprocess flow, and output/result persistence checks.

## Acceptance Mapping to Task 01/Plan Requirements

- Covers FR-3/FR-4/FR-5 by defining validation scope, one-build/one-run flow, and persisted results.
- Keeps dependency removals proof-gated by staged runtime evidence in later tasks.
