# Requirements — Migrate NoteLM to `vllm/vllm-openai:v0.18.0`

## Functional Requirements

### FR-1: Docker Base Image Must Migrate to the vLLM OpenAI Image
- The main project `Dockerfile` must replace the current PyTorch CUDA runtime base with `vllm/vllm-openai:v0.18.0` unless Task 01 produces explicit proof that a blocker prevents the migration.
- The migration must keep the existing NoteLM runtime contract intact for MinerU parsing, NoteLM post-processing, model cache paths, and handler startup.
- Docker build steps must document which packages are already provided by the new base image versus which packages still need to be installed by NoteLM.
- The plan must explicitly audit every dependency installed directly in `Dockerfile`, including apt-installed OS packages, explicit `pip install` steps, and any build toolchain packages, and classify each one as required, validation-pending, or removable.
- The plan must explicitly revalidate all Dockerfile assumptions that were previously tied to the old `pytorch/pytorch` base image, including Python toolchain availability, CUDA user-space behavior, apt package availability, and user setup.

### FR-2: Runtime Dependencies Must Be Audited and Reduced
- Every dependency currently listed in `requirements.txt` must be classified as one of: direct NoteLM dependency, required transitive pin, Docker/build-only dependency, validation-only dependency, or removable legacy dependency.
- Dependencies that are no longer required for the current `vlm-http-client` + local vLLM-server architecture must be removed.
- The audit must include Python requirements, explicit Docker-installed Python packages, and Docker-installed OS/tooling packages, especially `paddlepaddle-gpu` and any packages potentially duplicated by the `vllm/vllm-openai:v0.18.0` base image.
- The plan must require proof before removal: direct code import usage, CLI/runtime smoke checks, or successful Docker validation without the dependency.
- The plan must distinguish between dependencies that are unnecessary for NoteLM source code and dependencies that remain necessary because MinerU extras or runtime subprocesses still require them.

### FR-2a: Docker Image Contents Must Be Minimized to Required Runtime Assets
- The final migrated Docker image must install only the models that are actually required for the supported NoteLM runtime flow.
- The plan must require explicit review of model download steps in `Dockerfile` so obsolete or redundant model artifacts are not kept by default.
- If any model or package remains installed for future-proofing rather than current runtime necessity, the plan must record and justify that decision explicitly.

### FR-3: MinerU and vLLM Behavior Must Be Validated in the New Docker Image
- The migrated Docker image must be validated with checks that prove MinerU and vLLM still work together for the NoteLM processing flow.
- Validation must cover at least: dependency sanity, vLLM/MinerU command availability, server readiness behavior, and one end-to-end NoteLM processing smoke run that confirms markdown output is produced.
- The validation plan must explicitly confirm that the current MinerU integration path (`backend="vlm-http-client"`) remains functional in the migrated image.
- The validation flow must provide enough evidence to decide whether previously explicit dependencies, including local Paddle installation, are still required.

### FR-4: Docker Validation Must Use One Image Build and One Container Run
- The test workflow must build the Docker image once and reuse that single built image for all Docker-based validation steps.
- The preferred workflow is to evolve `test/run.sh` into the canonical Docker validation entrypoint, unless Task 01 proves that a small companion script is required to keep the harness maintainable.
- All in-container checks must run sequentially inside one container lifecycle instead of repeatedly starting separate containers for each check.
- The plan must define the exact orchestration mechanism for those sequential checks, such as a mounted shell or Python validation script invoked by `docker run`.

### FR-5: Validation Results Must Persist Outside the Container
- The Docker validation workflow must write structured results and logs to a host-mounted path so failures can be inspected locally after the container exits.
- The results artifact must include the executed checks, their pass/fail status, and enough captured output to support follow-up bug fixing.
- The plan must require result persistence even when one of the in-container checks fails.

### FR-6: Supporting Docs and Dependency Checks Must Stay Aligned
- Any dependency removals or Docker/runtime workflow changes must be reflected in `check_dependencies.py`, `README.md`, and the Docker validation harness.
- The plan must ensure that dependency verification logic matches the new expected runtime environment instead of the old PyTorch/Paddle-oriented assumptions.

## Non-Functional Requirements

### NFR-1: Reproducibility
- Docker build inputs and package versions must remain pinned where the project already uses version pinning.
- The migration plan must avoid introducing interactive install or download steps.

### NFR-2: Efficient Validation
- The Docker validation harness must minimize redundant setup work by avoiding repeated image builds, repeated dependency downloads, and repeated container starts.
- The results artifact format must make it easy to review failures without rerunning the entire suite blindly.

### NFR-3: Clear Failure Diagnostics
- Validation failures must surface which stage failed: image build, dependency check, server startup, MinerU CLI smoke, or NoteLM end-to-end processing.
- The plan must require actionable logging rather than silent failure or missing context.

### NFR-4: Minimal Scope Drift
- The migration effort must stay focused on the Docker image, dependency alignment, and Docker-based validation workflow.
- The plan must treat unrelated runtime refactors as out of scope unless they are required to make the migrated image work.

## Edge Cases and Pitfalls

1. **Base Image Capability Mismatch**
   - `vllm/vllm-openai:v0.18.0` may already include Python, CUDA libraries, and some Python packages that overlap with current NoteLM installs; the migration must avoid redundant or conflicting installs.
2. **Dockerfile Dependency Sprawl**
   - Some apt packages, build tools, or explicitly pip-installed packages may only exist because of the old base image or earlier runtime paths and must not be kept without proof.
3. **Paddle Ambiguity**
   - MinerU upstream does not treat local Paddle as mandatory for the current `vlm-http-client` flow, but NoteLM must prove removal safety before deleting the explicit install.
4. **Dependency Hidden Behind Subprocesses**
   - Some packages may not be imported directly by NoteLM code but may still be required by `mineru` CLIs, `vllm`, or startup checks.
5. **Model Scope Drift**
   - The Docker image may currently download more model assets than the supported NoteLM runtime actually needs; the migration must verify required-vs-legacy model scope before keeping downloads.
6. **Container Validation Harness Losing Logs on Failure**
   - If the container exits early, logs/results must still be written to the mounted host path.
7. **Interactive Docker Run Flags**
   - The current `test/run.sh` uses `-it`; the migrated harness must remain suitable for non-interactive automated execution.
8. **Host vs. Container Environment Drift**
   - Dependency conclusions must be based on the migrated container runtime, not only the local macOS development environment.
9. **Model and Cache Path Assumptions**
   - Model download locations, Hugging Face cache mounts, and `mineru.json` paths must continue to match what MinerU and NoteLM expect inside the new base image.
10. **Results Artifact Size or Fragmentation**
   - The validation workflow should prefer one consolidated results file or one clearly grouped results directory instead of scattering logs across many ad hoc paths.

## Definition of Done

1. A concrete implementation plan exists under `plans/migrate-to-vllm-docker-image/` with requirements, design, and ordered tasks.
2. The plan explicitly covers migration of `Dockerfile` to `vllm/vllm-openai:v0.18.0`.
3. The plan explicitly covers a dependency audit for `requirements.txt` plus dependencies installed directly by `Dockerfile`, including Docker-installed Python packages, apt packages, and proof criteria for removal.
4. The plan explicitly covers pruning the Docker image to only required models and truly required dependencies, with explicit justification for anything retained beyond the proven runtime path.
5. The plan explicitly covers validation of MinerU, vLLM, and one NoteLM end-to-end processing flow in the new Docker image.
6. The plan explicitly requires building the Docker image once and running all Docker validation checks in one container lifecycle.
7. The plan explicitly prefers adapting `test/run.sh` as the main validation entrypoint.
8. The plan explicitly requires validation results to be persisted to a host-mounted file or directory for local review.
9. The plan explicitly covers alignment updates for `check_dependencies.py` and `README.md` when implementation changes alter the expected runtime contract.
10. The plan records the current uncertainty around local Paddle and other legacy dependencies as validation questions to resolve rather than assumptions.

## Execution Status Note (2026-04-11)

- FR-1/FR-2 Docker cleanup execution has been completed: explicit `paddlepaddle-gpu==3.3.0` install was removed and legacy apt/toolchain packages were pruned from `Dockerfile`.
- Local runtime validation of the rebuilt `notelm` image confirmed dependency checks and startup import sanity still pass for the supported `vlm-http-client` path.
- FR-2 cleanup execution has been completed: `requirements.txt` now contains only project-managed dependencies.
- Removed base-image-provided requirements and ownership/risk/evidence details are documented in `plans/migrate-to-vllm-docker-image/artifacts/dependency-decisions.md`.
