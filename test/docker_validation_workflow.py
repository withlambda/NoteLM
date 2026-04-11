#!/usr/bin/env python3

import json
import os
import shlex
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional
from urllib import error, request


FALSE_VALUES = {"0", "false", "no", "off", ""}
STABLE_STAGE_ORDER = [
    "debug-deps-default",
    "deps",
    "cli-smoke",
    "server-readiness",
    "e2e-output",
    "runtime-assets",
    "debug-deps-true",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ValidationContext:
    results_dir: Path
    stages_dir: Path
    input_dir: Path
    output_dir: Path
    debug_true_enabled: bool
    readiness_timeout_seconds: int
    readiness_poll_interval_seconds: float


@dataclass(frozen=True)
class StageSpec:
    stage_id: str
    description: str
    runner: Callable[[ValidationContext, Path], tuple[bool, dict]]
    should_run: bool = True
    skip_reason: Optional[str] = None


def _log_command(log_file, command: list[str]) -> None:
    rendered_command = " ".join(shlex.quote(part) for part in command)
    log_file.write(f"$ {rendered_command}\n")


def run_command(
    command: list[str],
    log_path: Path,
    env_override: Optional[dict[str, str]] = None,
    cwd: Optional[Path] = None,
) -> int:
    stage_env = os.environ.copy()
    if env_override:
        stage_env.update(env_override)

    with log_path.open("a", encoding="utf-8") as log_file:
        _log_command(log_file, command)
        process = subprocess.run(
            command,
            check=False,
            cwd=str(cwd) if cwd else None,
            env=stage_env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )
        log_file.write(f"\n[exit_code={process.returncode}]\n")

    return process.returncode


def run_debug_dependency_default_stage(context: ValidationContext, log_path: Path) -> tuple[bool, dict]:
    del context
    current_debug = os.getenv("DEBUG", "false").strip().lower()
    debug_default_ok = current_debug in FALSE_VALUES

    command = [
        sys.executable,
        "-c",
        "from debug_dependencies import run_debug_dependency_check_if_enabled; run_debug_dependency_check_if_enabled()",
    ]
    command_exit = run_command(command, log_path, env_override={"DEBUG": "false"})
    success = debug_default_ok and command_exit == 0

    return success, {
        "current_debug": os.getenv("DEBUG", "false"),
        "expected_default_debug": "false",
        "debug_gate_probe_exit_code": command_exit,
    }


def run_dependency_stage(context: ValidationContext, log_path: Path) -> tuple[bool, dict]:
    del context
    command = [sys.executable, "check_dependencies.py"]
    command_exit = run_command(command, log_path)
    return command_exit == 0, {"command_exit_code": command_exit}


def run_cli_smoke_stage(context: ValidationContext, log_path: Path) -> tuple[bool, dict]:
    del context
    commands = [
        [sys.executable, "-m", "mineru.cli.client", "--help"],
        [sys.executable, "-m", "mineru.cli.vlm_server", "openai_server", "--help"],
        ["mineru-api", "--help"],
        ["mineru-openai-server", "--help"],
    ]

    failures: list[dict[str, object]] = []
    for command in commands:
        command_exit = run_command(command, log_path)
        if command_exit != 0:
            failures.append(
                {
                    "command": command,
                    "exit_code": command_exit,
                }
            )

    return not failures, {"failures": failures}


def _http_ready(url: str) -> bool:
    try:
        with request.urlopen(url, timeout=2) as response:
            return 200 <= response.status < 500
    except (error.URLError, TimeoutError):
        return False


def run_server_readiness_stage(context: ValidationContext, log_path: Path) -> tuple[bool, dict]:
    served_model_name = os.getenv("MINERU_VL_MODEL_NAME", "opendatalab/MinerU2.5-2509-1.2B")
    host = os.getenv("VALIDATION_SERVER_HOST", "127.0.0.1")
    port = int(os.getenv("VALIDATION_SERVER_PORT", os.getenv("NOTELM_VLLM_PORT", "8001")))

    command = [
        sys.executable,
        "-m",
        "mineru.cli.vlm_server",
        "openai_server",
        "--served-model-name",
        served_model_name,
        "--host",
        host,
        "--port",
        str(port),
    ]

    with log_path.open("a", encoding="utf-8") as log_file:
        _log_command(log_file, command)
        process = subprocess.Popen(
            command,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
            env=os.environ.copy(),
        )

    health_url = f"http://{host}:{port}/health"
    models_url = f"http://{host}:{port}/v1/models"
    deadline = time.monotonic() + context.readiness_timeout_seconds
    ready = False
    failure_reason = "unknown"

    try:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                failure_reason = f"server exited early with code {process.returncode}"
                break

            if _http_ready(health_url) and _http_ready(models_url):
                ready = True
                break

            time.sleep(context.readiness_poll_interval_seconds)

        if not ready and failure_reason == "unknown":
            failure_reason = (
                f"timeout waiting for readiness after {context.readiness_timeout_seconds} seconds"
            )
    finally:
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(f"\n[server_exit_code={process.returncode}]\n")

    return ready, {
        "host": host,
        "port": port,
        "health_url": health_url,
        "models_url": models_url,
        "failure_reason": None if ready else failure_reason,
    }


def run_e2e_output_stage(context: ValidationContext, log_path: Path) -> tuple[bool, dict]:
    command = [sys.executable, "test-handler.py"]
    command_exit = run_command(command, log_path)

    markdown_files = sorted(str(path.relative_to(context.output_dir)) for path in context.output_dir.rglob("*.md"))
    manifest_path = context.results_dir / "output-manifest.json"
    manifest_path.write_text(
        json.dumps({"markdown_files": markdown_files}, indent=2) + "\n",
        encoding="utf-8",
    )

    success = command_exit == 0 and bool(markdown_files)
    return success, {
        "handler_exit_code": command_exit,
        "markdown_count": len(markdown_files),
        "manifest": str(manifest_path.relative_to(context.results_dir)),
    }


def _path_has_files(path: Path) -> bool:
    if not path.exists() or not path.is_dir():
        return False
    return any(path.iterdir())


def run_runtime_assets_stage(context: ValidationContext, log_path: Path) -> tuple[bool, dict]:
    checks = {
        "mineru_vlm_model_dir": {
            "path": "/app/models/mineru/vlm",
            "required": True,
        },
        "datalab_cache_dir": {
            "path": "/app/cache/datalab",
            "required": False,
        },
        "hf_cache_mount": {
            "path": "/v/huggingface-cache",
            "required": False,
        },
    }

    evaluated: dict[str, dict[str, object]] = {}
    required_ok = True
    for name, item in checks.items():
        path = Path(item["path"])
        exists = path.exists()
        has_files = _path_has_files(path)
        evaluated[name] = {
            "path": str(path),
            "required": item["required"],
            "exists": exists,
            "has_files": has_files,
        }
        if item["required"] and not (exists and has_files):
            required_ok = False

    runtime_asset_report = context.results_dir / "runtime-assets.json"
    runtime_asset_report.write_text(
        json.dumps(evaluated, indent=2) + "\n",
        encoding="utf-8",
    )

    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(evaluated, indent=2))
        log_file.write("\n")

    return required_ok, {
        "report": str(runtime_asset_report.relative_to(context.results_dir)),
        "required_paths_ok": required_ok,
    }


def run_debug_dependency_true_stage(context: ValidationContext, log_path: Path) -> tuple[bool, dict]:
    del context
    command = [
        sys.executable,
        "-c",
        "from debug_dependencies import run_debug_dependency_check_if_enabled; run_debug_dependency_check_if_enabled()",
    ]
    command_exit = run_command(command, log_path, env_override={"DEBUG": "true"})
    return command_exit == 0, {
        "debug_true_enabled": True,
        "command_exit_code": command_exit,
    }


def build_stage_specs(context: ValidationContext) -> list[StageSpec]:
    return [
        StageSpec(
            stage_id="debug-deps-default",
            description="Verify debug-gated dependency behavior with default DEBUG=false",
            runner=run_debug_dependency_default_stage,
        ),
        StageSpec(
            stage_id="deps",
            description="Run runtime dependency sanity checks",
            runner=run_dependency_stage,
        ),
        StageSpec(
            stage_id="cli-smoke",
            description="Run MinerU/vLLM CLI smoke checks",
            runner=run_cli_smoke_stage,
        ),
        StageSpec(
            stage_id="server-readiness",
            description="Start vLLM serving path and verify readiness endpoints",
            runner=run_server_readiness_stage,
        ),
        StageSpec(
            stage_id="e2e-output",
            description="Execute NoteLM handler sample flow and verify markdown output",
            runner=run_e2e_output_stage,
        ),
        StageSpec(
            stage_id="runtime-assets",
            description="Confirm required runtime model/assets are present",
            runner=run_runtime_assets_stage,
        ),
        StageSpec(
            stage_id="debug-deps-true",
            description="Optional DEBUG=true dependency check path",
            runner=run_debug_dependency_true_stage,
            should_run=context.debug_true_enabled,
            skip_reason="Set VALIDATE_DEBUG_TRUE=1 to enable this stage.",
        ),
    ]


def execute_stage_specs(context: ValidationContext, stage_specs: list[StageSpec]) -> tuple[int, list[dict]]:
    records: list[dict] = []
    final_exit_code = 0
    prior_failure = False

    for stage in stage_specs:
        log_path = context.stages_dir / f"{stage.stage_id}.log"
        stage_started = utc_now_iso()
        duration_seconds = 0.0

        if prior_failure:
            with log_path.open("a", encoding="utf-8") as log_file:
                log_file.write("Stage skipped because a previous stage failed.\n")
            status = "skipped"
            details = {"reason": "previous_stage_failed"}
        elif not stage.should_run:
            with log_path.open("a", encoding="utf-8") as log_file:
                log_file.write(f"Stage skipped: {stage.skip_reason}\n")
            status = "skipped"
            details = {"reason": stage.skip_reason}
        else:
            timer_start = time.monotonic()
            try:
                success, details = stage.runner(context, log_path)
                status = "passed" if success else "failed"
            except Exception as exc:
                status = "failed"
                details = {
                    "error": str(exc),
                    "exception_type": type(exc).__name__,
                }
            duration_seconds = round(time.monotonic() - timer_start, 3)

            if status == "failed":
                final_exit_code = 1
                prior_failure = True

        records.append(
            {
                "stage_id": stage.stage_id,
                "description": stage.description,
                "status": status,
                "started_at": stage_started,
                "finished_at": utc_now_iso(),
                "duration_seconds": duration_seconds,
                "log": str(log_path.relative_to(context.results_dir)),
                "details": details,
            }
        )

    return final_exit_code, records


def write_summary(
    context: ValidationContext,
    records: list[dict],
    workflow_started_at: str,
    final_exit_code: int,
) -> None:
    summary = {
        "workflow": "docker-single-run-validation",
        "workflow_started_at": workflow_started_at,
        "workflow_finished_at": utc_now_iso(),
        "final_exit_code": final_exit_code,
        "stage_order": STABLE_STAGE_ORDER,
        "stages": records,
    }
    (context.results_dir / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    results_dir = Path(os.getenv("VALIDATION_RESULTS_DIR", "/v/results")).resolve()
    stages_dir = results_dir / "stages"
    stages_dir.mkdir(parents=True, exist_ok=True)

    context = ValidationContext(
        results_dir=results_dir,
        stages_dir=stages_dir,
        input_dir=Path(os.getenv("VOLUME_ROOT_MOUNT_PATH", "/v")) / "input",
        output_dir=Path(os.getenv("VOLUME_ROOT_MOUNT_PATH", "/v")) / "output",
        debug_true_enabled=os.getenv("VALIDATE_DEBUG_TRUE", "0").strip() in {"1", "true", "yes"},
        readiness_timeout_seconds=int(os.getenv("VALIDATION_READINESS_TIMEOUT_SECONDS", "120")),
        readiness_poll_interval_seconds=float(os.getenv("VALIDATION_READINESS_POLL_SECONDS", "2")),
    )

    workflow_started_at = utc_now_iso()
    records: list[dict] = []
    final_exit_code = 1

    try:
        stage_specs = build_stage_specs(context)
        final_exit_code, records = execute_stage_specs(context, stage_specs)
    except Exception as exc:
        records = [
            {
                "stage_id": "debug-deps-default",
                "description": "Verify debug-gated dependency behavior with default DEBUG=false",
                "status": "failed",
                "started_at": utc_now_iso(),
                "finished_at": utc_now_iso(),
                "duration_seconds": 0.0,
                "log": "stages/debug-deps-default.log",
                "details": {
                    "reason": "workflow_internal_error",
                    "error": str(exc),
                },
            }
        ]

    write_summary(context, records, workflow_started_at, final_exit_code)
    return final_exit_code


if __name__ == "__main__":
    sys.exit(main())
