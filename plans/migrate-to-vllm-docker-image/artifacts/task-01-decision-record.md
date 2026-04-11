# Task 01 Decision Record — `migrate-to-vllm-docker-image`

## Decision

- **Gate result**: `go` (guarded)
- **Decision scope**: proceed to Task 02 migration work targeting `vllm/vllm-openai:v0.18.0`.

## Why This Is `go` (not `no-go`)

- No hard blocker was found that prevents attempting the base-image migration.
- Task 01 produced evidence-backed matrices for:
  - Python dependencies (`requirements.txt`)
  - Dockerfile direct installs (apt + pip)
  - Model/runtime artifacts
  - Validation architecture for one-build/one-run, non-interactive, persisted results
- Risky removals remain explicitly gated behind later proof (`validate-before-keep` / `validate-before-remove`), so migration can proceed without forcing premature deletions.

## Known Risks / Blockers to Resolve in Downstream Tasks

1. **`mineru[vllm]` extra vs direct `vllm==0.18.0` strategy mismatch**
   - Evidence: `mineru==3.0.7` extra metadata adds `vllm>=0.10.1.1,<0.12`, while project pins `vllm==0.18.0`.
   - Impact: dependency resolution and deterministic environment policy must be normalized.
   - Planned resolution: Task 03 (`requirements` + dependency-check alignment).

2. **Legacy dependency carryovers may be obsolete on vLLM base image**
   - Includes: `paddlepaddle-gpu`, portions of apt/toolchain stack, selected transitive pins.
   - Impact: image bloat and possible unnecessary complexity.
   - Planned resolution: Task 02/03/04 staged validation with proof-gated removals.

3. **Current validation harness is interactive and weakly structured**
   - Evidence: `test/run.sh` uses `docker run -it` and only verifies markdown file existence.
   - Impact: hard to automate and audit reproducibly.
   - Planned resolution: Task 04 single-run orchestrated validation with persisted result artifacts.

## Enforced Guardrails for Tasks 02+

- Do not remove `paddlepaddle-gpu`, apt/toolchain packages, or transitive Python pins without staged runtime proof.
- Keep `check_dependencies.py` as fast availability gate; move heavy readiness/E2E checks to Docker smoke workflow.
- Preserve deterministic MinerU model/config wiring (`MinerU2.5-2509-1.2B`, `/app/mineru.json`) unless replacement is fully evidenced.
- Ensure final validation remains one-build/one-run and non-interactive with host-visible results.

## Fallback Path (if migration fails in Task 02/04)

- Temporarily retain current PyTorch-based base image path while applying only non-breaking improvements:
  - improved validation orchestration and result persistence,
  - dependency checks split/clarification,
  - explicit evidence collection for each contested package.
- Re-attempt base-image migration once blocker evidence is resolved.
