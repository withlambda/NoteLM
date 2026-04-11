import logging
import os
import signal
import subprocess
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

import requests


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VllmServerRoleConfig:
    role: str
    command: list[str]
    host: str
    port: int
    startup_timeout: int
    health_check_interval: float
    shutdown_grace_period: int
    expected_model_id: Optional[str] = None
    environment: Dict[str, str] = field(default_factory=dict)

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"


class VllmServerManager:
    def __init__(self) -> None:
        self._role_configs: Dict[str, VllmServerRoleConfig] = {}
        self._processes: Dict[str, subprocess.Popen] = {}

    def set_role_config(self, config: VllmServerRoleConfig) -> None:
        self._role_configs[config.role] = config

    def get_process(self, role: str) -> Optional[subprocess.Popen]:
        process = self._processes.get(role)
        if process is None:
            return None
        if process.poll() is not None:
            self._processes.pop(role, None)
            return None
        return process

    def is_running(self, role: str) -> bool:
        return self.get_process(role) is not None

    def start(self, role: str, startup_delay: float = 0.0) -> subprocess.Popen:
        config = self._role_configs[role]

        for running_role, process in list(self._processes.items()):
            if process.poll() is not None:
                self._processes.pop(running_role, None)
                continue
            if running_role != role:
                raise RuntimeError(
                    f"Cannot start VLM server role '{role}' while role '{running_role}' is still running."
                )

        existing = self.get_process(role)
        if existing is not None:
            return existing

        if startup_delay > 0:
            time.sleep(startup_delay)

        env = os.environ.copy()
        env.update(config.environment)
        process = subprocess.Popen(
            config.command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )
        self._processes[role] = process
        self.wait_ready(role)
        return process

    def wait_ready(self, role: str) -> None:
        config = self._role_configs[role]
        process = self.get_process(role)
        if process is None:
            raise RuntimeError(f"VLM server role '{role}' is not running.")

        deadline = time.time() + config.startup_timeout
        health_url = f"{config.base_url}/health"
        models_url = f"{config.base_url}/v1/models"
        last_error: Optional[Exception] = None

        while time.time() < deadline:
            if process.poll() is not None:
                stdout, _ = process.communicate(timeout=2)
                raise RuntimeError(
                    f"VLM server role '{role}' exited unexpectedly with code {process.returncode}. "
                    f"Output: {stdout.strip()}"
                )

            try:
                health_response = requests.get(health_url, timeout=2)
                if health_response.status_code != 200:
                    time.sleep(config.health_check_interval)
                    continue

                if config.expected_model_id:
                    model_response = requests.get(models_url, timeout=2)
                    model_response.raise_for_status()
                    payload = model_response.json()
                    model_ids = {
                        model_entry.get("id")
                        for model_entry in payload.get("data", [])
                        if isinstance(model_entry, dict)
                    }
                    if config.expected_model_id not in model_ids:
                        raise RuntimeError(
                            f"Expected served model id '{config.expected_model_id}' for role '{role}', "
                            f"found {sorted(model_ids)}"
                        )

                return
            except Exception as exc:
                last_error = exc
                time.sleep(config.health_check_interval)

        raise TimeoutError(
            f"Timed out waiting for VLM server role '{role}' readiness after {config.startup_timeout}s"
        ) from last_error

    def wait_for_server_ready(self, role: str, retry_count: int, retry_delay: float) -> None:
        """Wait for a managed server role after startup, retrying if readiness is delayed."""
        total_attempts = retry_count + 1

        for attempt in range(1, total_attempts + 1):
            try:
                logger.info(
                    "Checking readiness for VLM server role '%s' (attempt %s/%s).",
                    role,
                    attempt,
                    total_attempts,
                )
                self.wait_ready(role)
                return
            except Exception as exc:
                if attempt >= total_attempts:
                    raise RuntimeError(
                        f"VLM server role '{role}' did not become ready after {total_attempts} attempts."
                    ) from exc

                logger.warning(
                    "VLM server role '%s' was not ready on attempt %s/%s: %s. Retrying in %.2f seconds.",
                    role,
                    attempt,
                    total_attempts,
                    exc,
                    retry_delay,
                )
                time.sleep(retry_delay)

    def stop(self, role: str) -> None:
        process = self._processes.get(role)
        if process is None:
            return

        config = self._role_configs[role]

        if process.poll() is None:
            process.send_signal(signal.SIGTERM)
            try:
                process.wait(timeout=config.shutdown_grace_period)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

        self._processes.pop(role, None)

    def handoff(self, parse_role: str, post_role: str, cooldown_seconds: int = 0) -> None:
        self.stop(parse_role)

        if self.is_running(parse_role):
            raise RuntimeError(
                f"Cannot handoff to role '{post_role}' because role '{parse_role}' is still running."
            )

        if cooldown_seconds > 0:
            time.sleep(cooldown_seconds)

        if self.is_running(parse_role):
            raise RuntimeError(
                f"Cannot handoff to role '{post_role}' because role '{parse_role}' became active again."
            )
