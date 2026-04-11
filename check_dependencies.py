import importlib
import logging
import os
import subprocess
import sys
from typing import Sequence


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def check_import(module_name: str) -> bool:
    """Import a module and return whether it is importable."""
    try:
        importlib.import_module(module_name)
        logger.info("✅ Success: '%s' imported.", module_name)
        return True
    except ImportError:
        logger.exception("❌ Error: '%s' NOT found.", module_name)
        return False


def run_command_check(
    command: Sequence[str],
    description: str,
    *,
    timeout: int = 30,
    env: dict[str, str] | None = None,
) -> bool:
    """Run a command and return whether it exits with status 0."""
    logger.info("Checking %s: `%s`", description, " ".join(command))
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        logger.exception("❌ Error: %s timed out after %s seconds.", description, timeout)
        return False
    except OSError:
        logger.exception("❌ Error: failed to execute %s.", description)
        return False

    if result.returncode == 0:
        logger.info("✅ Success: %s.", description)
        return True

    logger.error("❌ Error: %s failed with exit code %s.", description, result.returncode)
    if result.stdout:
        logger.error("--- stdout ---\n%s\n--------------", result.stdout)
    if result.stderr:
        logger.error("--- stderr ---\n%s\n--------------", result.stderr)
    return False


def check_vllm_entrypoint() -> bool:
    """Check that vLLM OpenAI API server module can be imported."""
    env = os.environ.copy()
    env["VLLM_TARGET_DEVICE"] = "cpu"
    env["VLLM_DEVICE"] = "cpu"
    env["VLLM_CONFIGURE_LOGGING"] = "0"
    env["VLLM_LOGGING_LEVEL"] = "ERROR"

    logger.info(
        "Checking vLLM entrypoint imports ('python3 -c \"import vllm.entrypoints.openai.api_server\"')..."
    )
    try:
        result = subprocess.run(
            ["python3", "-c", "import vllm.entrypoints.openai.api_server"],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
    except subprocess.TimeoutExpired:
        logger.exception("❌ Error: vLLM entrypoint import check timed out.")
        return False
    except OSError:
        logger.exception("❌ Error: failed to execute vLLM entrypoint import check.")
        return False

    if result.returncode == 0:
        logger.info("✅ Success: vLLM entrypoint imports are working.")
        return True

    stderr = result.stderr or ""
    if "RuntimeError: Failed to infer device type" in stderr and "ModuleNotFoundError" not in stderr:
        logger.warning(
            "⚠️  Warning: vLLM entrypoint import triggered device inference failure in build environment, "
            "but no ModuleNotFoundError was detected."
        )
        return True

    logger.error("❌ Error: vLLM entrypoint import failed with exit code %s.", result.returncode)
    if result.stderr:
        logger.error("--- stderr ---\n%s\n--------------", result.stderr)
    return False


def main() -> None:
    lightweight_modules_to_check = [
        "uvloop",
        "psutil",
        "requests",
        "mineru",
        "mineru.cli.client",
        "mineru.cli.fast_api",
        "mineru.cli.vlm_server",
        "runpod",
        "openai",
        "httpx",
        "tiktoken",
        "pydantic",
        "pydantic_settings",
        "json_repair",
        "langchain_text_splitters",
        "huggingface_hub",
        "langdetect",
    ]

    lightweight_command_checks = [
        (["python3", "-m", "mineru.cli.client", "--help"], "MinerU client CLI module availability"),
        (
            ["python3", "-m", "mineru.cli.vlm_server", "openai_server", "--help"],
            "MinerU vLLM server CLI module availability",
        ),
        (["mineru-api", "--help"], "`mineru-api` command availability"),
        (["mineru-openai-server", "--help"], "`mineru-openai-server` command availability"),
    ]

    bounded_runtime_smoke_checks = [
        (
            [
                "python3",
                "-m",
                "mineru.cli.vlm_server",
                "openai_server",
                "--served-model-name",
                "opendatalab/MinerU2.5-2509-1.2B",
                "--help",
            ],
            "MinerU vLLM served-model-name wiring smoke check",
        )
    ]

    all_ok = True
    logger.info("--- Starting Dependency Check ---")

    for module_name in lightweight_modules_to_check:
        if not check_import(module_name):
            all_ok = False

    # vLLM is intentionally Docker/base-image-managed (not `requirements.txt`-managed),
    # but remains a strict runtime dependency for this service.
    if "vllm" in sys.modules or check_import("vllm"):
        if not check_vllm_entrypoint():
            all_ok = False
    else:
        all_ok = False

    for command, description in lightweight_command_checks:
        if not run_command_check(command, description):
            all_ok = False

    for command, description in bounded_runtime_smoke_checks:
        if not run_command_check(command, description):
            all_ok = False

    logger.info("---------------------------------")
    if all_ok:
        logger.info("🎉 All critical dependencies are verified!")
        sys.exit(0)

    logger.error("🛑 Missing or broken dependencies found!")
    sys.exit(1)


if __name__ == "__main__":
    main()
