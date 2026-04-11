import logging
import os


logger = logging.getLogger(__name__)


def is_debug_enabled() -> bool:
    return os.getenv("DEBUG", "false").strip().lower() in {"1", "true", "yes", "on"}


def run_debug_dependency_check_if_enabled() -> None:
    if not is_debug_enabled():
        return

    logger.info("DEBUG=true detected, running dependency checks before starting handler.")
    from check_dependencies import main as check_dependencies_main

    check_dependencies_main()
