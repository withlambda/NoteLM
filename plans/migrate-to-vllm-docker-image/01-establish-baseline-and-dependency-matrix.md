# Task 01 — Establish the Docker Baseline and Dependency Matrix

## Dependencies
- None

## Requirements Traced
- FR-1 (base-image migration gate)
- FR-2 (dependency audit)
- FR-3 (validation scope definition)
- FR-4 (single-build/single-run validation design)
- FR-5 (result persistence)
- NFR-1, NFR-2, NFR-3

## Implementation Steps

1. Re-read the current working-tree versions of the migration hotspots before editing:
   - `Dockerfile`
   - `requirements.txt`
   - `check_dependencies.py`
   - `test/run.sh`
   - `README.md`
2. Define analysis scope and source-of-truth boundaries before collecting dependency evidence:
   - treat the primary repository source tree as authoritative
   - explicitly exclude generated/copied build-context trees (for example `build/test/*`) from dependency-usage proof
   - record these scope rules in the dependency-matrix artifact header
3. Build a dependency matrix covering every explicit Python package and every dependency installed directly by `Dockerfile`:
   - Identify direct imports/usages in NoteLM source.
   - Identify packages required indirectly by MinerU/vLLM commands or subprocess flows.
   - Identify packages that may already be present in `vllm/vllm-openai:v0.18.0`.
   - Identify apt-installed OS packages and build tools that are runtime-critical versus legacy carryovers.
   - Mark packages as keep, validate-before-keep, validate-before-remove, or remove.
4. Treat the following items as mandatory proof targets rather than assumptions:
   - `paddlepaddle-gpu`
   - `vllm`
   - `cuda-bindings`
   - `psutil`
   - `shapely`
   - any extra package pulled by `mineru[vllm]`
   - current Dockerfile apt packages/toolchain packages
   - for each target, include one proof tuple: `(source evidence, runtime/CLI check, keep/remove recommendation, confidence, blocker-if-any)`
5. Build a model/artifact matrix for what the Docker image installs:
   - identify which downloaded models are required for the supported NoteLM runtime path
   - identify generated runtime config files that must remain
   - mark model artifacts as required, validate-before-keep, or removable
6. Define the future Docker validation contract before implementation:
   - one image build
   - one container run
   - sequential in-container checks
   - mounted results file or results directory
   - non-interactive execution
7. Decide whether `test/run.sh` alone remains readable enough as the orchestration surface or whether it should call one dedicated in-container validation helper.
8. Record which current checks belong to `check_dependencies.py` and which belong to the heavier Docker smoke workflow:
   - explicitly classify build-time checks versus runtime startup checks
   - capture the target rule that dependency checks are runtime-gated by `DEBUG` (default `false`) and not executed during Docker build
9. Emit a migration decision gate record for downstream tasks:
   - `go` (migration to `vllm/vllm-openai:v0.18.0`) or `no-go`
   - if `no-go`, include blocker evidence and a fallback execution path for the remaining plan

## Required Outputs/Artifacts

- `plans/migrate-to-vllm-docker-image/artifacts/dependency-matrix.md`
- `plans/migrate-to-vllm-docker-image/artifacts/model-artifact-matrix.md`
- `plans/migrate-to-vllm-docker-image/artifacts/validation-contract.md`
- `plans/migrate-to-vllm-docker-image/artifacts/task-01-decision-record.md`

## Test Requirements
- Validate the dependency matrix against actual source imports, runtime entrypoints, known MinerU/vLLM CLI usage, and direct Dockerfile install steps rather than guesswork.
- Validate that the proposed Docker validation contract covers all user-requested goals: MinerU, vLLM, NoteLM processing, one build, one run, persisted results.
- Validate that any planned dependency removals remain gated on later proof and are not treated as already settled facts.
- Validate that the model/artifact matrix distinguishes required runtime assets from image bloat candidates.
- Validate that Task 01 artifacts are produced at the declared paths and include enough evidence for a downstream go/no-go migration decision.
