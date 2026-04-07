# Task 01 — Select MinerU/vLLM Server Orchestration Path

## Dependencies
- None (first task)

## Requirements Traced
- FR-2 (background vLLM server lifecycle)
- FR-6 (must support and choose one orchestration path)
- NFR-2 (deterministic startup/failure behavior)
- EC-1, EC-2, EC-3 (port conflicts, readiness race, model-name mismatch)

## Implementation Steps

1. Inventory official MinerU orchestration helpers first:
   - Confirm how `mineru.cli.client.run_orchestrated_cli()` starts local `mineru-api` automatically when `api_url` is omitted.
   - Confirm how `mineru.cli.api_client.LocalAPIServer` launches `mineru.cli.fast_api` and how readiness is checked.
   - Confirm that `mineru-openai-server` is the official OpenAI-compatible VLM-serving entrypoint and identify required flags.
2. Validate the preferred MinerU-native path feasibility:
   - Verify the exact runtime contract for `mineru-api` base URL vs. OpenAI-compatible `server_url`.
   - Verify how model name/path can be aligned with `MINERU_VL_MODEL_NAME`.
   - Prove the actual served model identifier exposed by the selected serving path instead of assuming it matches the model weight source string.
   - Verify which MinerU `3.0.7` package extras are sufficient for this path and whether official scripts remain available.
3. Determine how MinerU itself handles concurrency and adopt or constrain it explicitly:
   - Confirm that non-pipeline workloads are planned as one document per task and submitted to one shared service with bounded concurrency.
   - Prefer delegating parse-task concurrency entirely to MinerU’s client/API server-side orchestration; do not retain NoteLM outer multiprocessing if that delegation is feasible.
   - If Option A stays feasible, require full delegation by handing one input directory to one MinerU orchestration entrypoint; do not mirror MinerU task submission inside NoteLM.
   - If full delegation is not feasible, record the blocking reason, set the fallback outer-parallelism cap explicitly, and record the GPU oversubscription guardrails required for NoteLM.
4. Decide implementation path with explicit rationale:
   - First choice: MinerU-native local API orchestration + official `mineru-openai-server`.
   - Fallback: direct `do_parse` / `aio_do_parse` + official `mineru-openai-server`.
   - Last resort: NoteLM-managed `vllm serve` routed through the shared `vllm_server.py` manager.
   - Update `design.md` by completing the `Selected Integration Contract` section, even if Option A remains the winner.
5. Define the exact runtime contract for downstream tasks:
   - API host/port source of truth.
   - OpenAI-compatible server host/port source of truth.
   - Explicit ownership split: external OpenAI-compatible server is for MinerU parsing only, while NoteLM keeps its own post-processing server lifecycle.
   - Served model name source of truth.
   - Observed served-model identifier proof and how it maps to `MINERU_VL_MODEL_NAME`.
   - `MINERU_MODEL_SOURCE` source of truth.
   - Exact owner of parse-task concurrency and task partitioning.
   - Startup timeout and health endpoint behavior for both services.
   - Mandatory sequential-only rule: MinerU parsing VLM server must stop fully before any post-processing VLM server starts.
   - Exact shutdown/wait behavior and the guardrail used to treat VRAM as released before the second server can start: process exit observed, `gc.collect()` run, CUDA cache cleanup attempted when available, configured cooldown elapsed, and post-processing startup denied if the first process is still alive or the next server cannot become healthy within the retry budget.
   - Exact port assignments for the parse phase and post-processing phase, even if one port is reused sequentially.
   - Exact shared `vllm_server.py` class/interface that will start both VLM-serving roles, with an explicit statement that `mineru-api` lifecycle ownership is outside that manager boundary.
   - Exact parse output artifact contract preserved or intentionally redefined for downstream post-processing, including markdown-path discovery, image placement, and one deterministic input-to-output mapping.
   - Exact legacy settings to remove or reject so the old NoteLM parse-pool contract cannot survive the refactor.
   - Canonical removed-legacy-keys list and exact rejection mode/layer for those keys.
6. Produce explicit dependency proof for the selected path:
   - Name the exact candidate MinerU `3.0.7` requirement string/extras to use in NoteLM.
   - Record how availability of required official MinerU modules/scripts will be proven (`import`, CLI `--help`, subprocess smoke check, or a combination).
   - Record one minimal usability proof for the selected path after install, separate from the availability proof.
   - Record the exact commands/modules to be checked.

## Test Requirements
- Provide a command-level dry-run proof that the selected MinerU-native path can be constructed with current settings.
- Confirm chosen path has explicit health-readiness checks before MinerU requests are sent.
- Confirm startup failure path is explicit (non-zero failure and actionable logs).
- Confirm the selected path is supported by MinerU `3.0.7` package scripts/modules available to NoteLM.
- Confirm the decision artifact in `design.md` captures selected option, rejected options, exact commands/functions, env vars, health endpoints, timeouts, the explicit MinerU-only external server decision, the retained NoteLM post-processing server decision, the strict no-parallel handoff/VRAM-release rule, the shared `vllm_server.py` manager contract limited to VLM-serving processes, the exact parse-concurrency owner/full-delegation decision, the parse output artifact contract, the observed served-model identifier proof, and the removed/rejected legacy settings plus rejection mode.
