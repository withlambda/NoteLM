import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import handler


class _FakeConfig:
    def __init__(self, root: Path, use_postprocess_llm: bool) -> None:
        self.use_postprocess_llm = use_postprocess_llm
        self.volume_root_mount_path = root
        self.cleanup_output_dir_before_start = True
        self.VALID_OUTPUT_FORMATS = {"markdown"}
        self.ALLOWED_INPUT_FILE_EXTENSIONS = {".pdf"}
        self.FILE_ENCODING = "utf-8"
        self.LANGUAGE_DETECTION_SAMPLE_SIZE = 2000
        self.IMAGE_FILE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
        self.image_description_section_heading = "## Extracted Image Descriptions"
        self.image_description_heading = "**[BEGIN IMAGE DESCRIPTION]**"
        self.image_description_end = "**[END IMAGE DESCRIPTION]**"


class _FakeProcess:
    def __init__(self, pid: int = 1000) -> None:
        self.pid = pid


class _RecordingManager:
    instances = []
    wait_ready_side_effects = []

    def __init__(self) -> None:
        self.calls = []
        self._running = set()
        self._configs = {}
        self._wait_ready_side_effects = list(type(self).wait_ready_side_effects)
        _RecordingManager.instances.append(self)

    def set_role_config(self, config):
        self.calls.append(("set_role_config", config.role))
        self._configs[config.role] = config

    def start(self, role: str, startup_delay: float = 0.0):
        self.calls.append(("start", role, startup_delay))
        self._running.add(role)
        return _FakeProcess()

    def stop(self, role: str):
        self.calls.append(("stop", role))
        self._running.discard(role)

    def wait_ready(self, role: str):
        self.calls.append(("wait_ready", role))
        if self._wait_ready_side_effects:
            outcome = self._wait_ready_side_effects.pop(0)
            if isinstance(outcome, BaseException):
                raise outcome
        return None

    def wait_for_server_ready(self, role: str, retry_count: int, retry_delay: float):
        total_attempts = retry_count + 1

        for attempt in range(1, total_attempts + 1):
            try:
                self.wait_ready(role)
                return
            except Exception as exc:
                if attempt >= total_attempts:
                    raise RuntimeError(
                        f"VLM server role '{role}' did not become ready after {total_attempts} attempts."
                    ) from exc
                handler.time.sleep(retry_delay)

    def handoff(self, parse_role: str, post_role: str, cooldown_seconds: int = 0):
        self.calls.append(("handoff", parse_role, post_role, cooldown_seconds))
        self._running.discard(parse_role)

    def get_process(self, role: str):
        if role in self._running:
            return _FakeProcess()
        return None

    def is_running(self, role: str) -> bool:
        return role in self._running


class _FakeVllmWorker:
    instances = []

    def __init__(self, settings, server_manager):
        self.settings = settings
        self.server_manager = server_manager
        self.entered = False
        _FakeVllmWorker.instances.append(self)

    def __enter__(self):
        self.entered = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.entered = False

    def process_file(self, file_path, prompt_template, max_chunk_workers):
        del prompt_template
        del max_chunk_workers
        return file_path.exists()

    def describe_images(self, image_paths, prompt_template, max_image_workers, target_language=None):
        del prompt_template
        del max_image_workers
        del target_language
        return [(path, "desc") for path in image_paths]


async def _mock_orchestrated_cli_success(**kwargs):
    input_path: Path = kwargs["input_path"]
    output_dir: Path = kwargs["output_dir"]
    for file_path in input_path.iterdir():
        if not file_path.is_file() or file_path.suffix.lower() != ".pdf":
            continue
        stem = file_path.stem
        nested_dir = output_dir / stem / stem
        nested_dir.mkdir(parents=True, exist_ok=True)
        (nested_dir / f"{stem}.md").write_text("parsed text", encoding="utf-8")


class TestHandlerOrchestration(unittest.TestCase):
    def setUp(self):
        _RecordingManager.instances.clear()
        _RecordingManager.wait_ready_side_effects = []
        _FakeVllmWorker.instances.clear()

    def _create_job_dirs(self, pdf_count: int = 1):
        tmpdir = tempfile.TemporaryDirectory()
        root = Path(tmpdir.name)
        input_dir = root / "input"
        output_dir = root / "output"
        input_dir.mkdir(parents=True, exist_ok=True)
        for index in range(pdf_count):
            (input_dir / f"doc-{index + 1}.pdf").write_bytes(b"%PDF-1.4")
        return tmpdir, root, input_dir, output_dir

    @patch("handler.log_vram_usage")
    @patch("handler.run_orchestrated_cli")
    @patch("handler.VllmServerManager", _RecordingManager)
    @patch("handler.time.sleep")
    def test_handler_retries_parse_server_readiness_before_orchestration(
        self,
        mock_sleep,
        mock_run_orchestrated_cli,
        mock_log_vram,
    ):
        del mock_log_vram
        _RecordingManager.wait_ready_side_effects = [TimeoutError("warming up"), None]
        mock_run_orchestrated_cli.side_effect = _mock_orchestrated_cli_success

        tmpdir, root, _, _ = self._create_job_dirs()
        try:
            fake_config = _FakeConfig(root=root, use_postprocess_llm=False)
            job = {
                "input": {
                    "input_dir": "input",
                    "output_dir": "output",
                    "mineru_backend": "vlm-http-client",
                    "mineru_server_ready_check_retries": 2,
                    "mineru_server_ready_check_delay": 0.5,
                }
            }

            with patch("handler.setup_config", return_value=fake_config):
                result = handler.handler(job)

            self.assertEqual(result["status"], "completed")
            self.assertEqual(mock_run_orchestrated_cli.call_count, 1)
            manager = _RecordingManager.instances[0]
            wait_ready_calls = [call for call in manager.calls if call[0] == "wait_ready"]
            self.assertEqual(wait_ready_calls, [("wait_ready", "mineru_parse"), ("wait_ready", "mineru_parse")])
            mock_sleep.assert_called_once_with(0.5)
        finally:
            tmpdir.cleanup()

    @patch("handler.log_vram_usage")
    @patch("handler.run_orchestrated_cli")
    @patch("handler.VllmServerManager", _RecordingManager)
    @patch("handler.time.sleep")
    def test_handler_raises_after_parse_server_readiness_retries_are_exhausted(
        self,
        mock_sleep,
        mock_run_orchestrated_cli,
        mock_log_vram,
    ):
        del mock_log_vram
        _RecordingManager.wait_ready_side_effects = [TimeoutError("warming up"), TimeoutError("still warming up")]

        tmpdir, root, _, _ = self._create_job_dirs()
        try:
            fake_config = _FakeConfig(root=root, use_postprocess_llm=False)
            job = {
                "input": {
                    "input_dir": "input",
                    "output_dir": "output",
                    "mineru_backend": "vlm-http-client",
                    "mineru_server_ready_check_retries": 1,
                    "mineru_server_ready_check_delay": 0.25,
                }
            }

            with patch("handler.setup_config", return_value=fake_config):
                with self.assertRaisesRegex(RuntimeError, "did not become ready after 2 attempts"):
                    handler.handler(job)

            self.assertFalse(mock_run_orchestrated_cli.called)
            manager_calls = _RecordingManager.instances[0].calls
            self.assertIn(("stop", "mineru_parse"), manager_calls)
            self.assertEqual(mock_sleep.call_count, 1)
            mock_sleep.assert_called_with(0.25)
        finally:
            tmpdir.cleanup()

    @patch("handler.log_vram_usage")
    @patch("handler.run_orchestrated_cli")
    @patch("handler.VllmServerManager", _RecordingManager)
    def test_handler_uses_orchestrated_vlm_http_client_path(self, mock_run_orchestrated_cli, mock_log_vram):
        del mock_log_vram

        async def _assert_running_and_parse(**kwargs):
            self.assertTrue(_RecordingManager.instances[0].is_running("mineru_parse"))
            await _mock_orchestrated_cli_success(**kwargs)

        mock_run_orchestrated_cli.side_effect = _assert_running_and_parse

        tmpdir, root, _, _ = self._create_job_dirs()
        try:
            fake_config = _FakeConfig(root=root, use_postprocess_llm=False)
            job = {
                "input": {
                    "doc_language": "latin",
                    "input_dir": "input",
                    "output_dir": "output",
                    "mineru_backend": "vlm-http-client",
                    "mineru_api_url": "http://127.0.0.1:18080",
                    "mineru_server_url": "http://127.0.0.1:30000",
                    "mineru_model_source": "local",
                    "mineru_vl_model_name": "opendatalab/MinerU2.5-2509-1.2B",
                }
            }

            with patch("handler.setup_config", return_value=fake_config):
                result = handler.handler(job)

            self.assertEqual(result["status"], "completed")
            self.assertTrue(mock_run_orchestrated_cli.called)
            kwargs = mock_run_orchestrated_cli.call_args.kwargs
            self.assertEqual(mock_run_orchestrated_cli.call_count, 1)
            self.assertEqual(kwargs["backend"], "vlm-http-client")
            self.assertEqual(kwargs["api_url"], "http://127.0.0.1:18080")
            self.assertEqual(kwargs["lang"], "latin")
            self.assertEqual(kwargs["server_url"], "http://127.0.0.1:30000")

            normalized_md = root / "output" / "doc-1" / "doc-1.md"
            self.assertTrue(normalized_md.exists())

            manager = _RecordingManager.instances[0]
            manager_calls = manager.calls
            self.assertIn(("start", "mineru_parse", 0.0), manager_calls)
            self.assertIn(("stop", "mineru_parse"), manager_calls)
            parse_config = manager._configs["mineru_parse"]
            self.assertIn("mineru.cli.vlm_server", parse_config.command)
            self.assertNotIn("openai_server", parse_config.command)
            self.assertNotIn("mineru-api", parse_config.command)
            self.assertEqual(parse_config.environment["MINERU_MODEL_SOURCE"], "local")
            self.assertEqual(parse_config.environment["MINERU_VL_MODEL_NAME"], "opendatalab/MinerU2.5-2509-1.2B")
        finally:
            tmpdir.cleanup()

    @patch("handler.log_vram_usage")
    @patch("handler.run_orchestrated_cli")
    @patch("handler.VllmServerManager", _RecordingManager)
    def test_handler_defaults_doc_language_to_english(self, mock_run_orchestrated_cli, mock_log_vram):
        del mock_log_vram
        mock_run_orchestrated_cli.side_effect = _mock_orchestrated_cli_success

        tmpdir, root, _, _ = self._create_job_dirs()
        try:
            fake_config = _FakeConfig(root=root, use_postprocess_llm=False)
            job = {
                "input": {
                    "input_dir": "input",
                    "output_dir": "output",
                    "mineru_backend": "vlm-http-client",
                }
            }

            with patch("handler.setup_config", return_value=fake_config):
                result = handler.handler(job)

            self.assertEqual(result["status"], "completed")
            self.assertEqual(mock_run_orchestrated_cli.call_args.kwargs["lang"], "en")
        finally:
            tmpdir.cleanup()

    @patch("handler.log_vram_usage")
    @patch("handler.run_orchestrated_cli")
    @patch("handler.VllmServerManager", _RecordingManager)
    def test_handler_keeps_parse_concurrency_under_single_orchestrated_cli_call(
        self,
        mock_run_orchestrated_cli,
        mock_log_vram,
    ):
        del mock_log_vram
        mock_run_orchestrated_cli.side_effect = _mock_orchestrated_cli_success

        tmpdir, root, _, _ = self._create_job_dirs(pdf_count=2)
        try:
            fake_config = _FakeConfig(root=root, use_postprocess_llm=False)
            job = {
                "input": {
                    "input_dir": "input",
                    "output_dir": "output",
                    "mineru_backend": "vlm-http-client",
                }
            }

            with patch("handler.setup_config", return_value=fake_config):
                result = handler.handler(job)

            self.assertEqual(result["status"], "completed")
            self.assertEqual(mock_run_orchestrated_cli.call_count, 1)
            self.assertTrue((root / "output" / "doc-1" / "doc-1.md").exists())
            self.assertTrue((root / "output" / "doc-2" / "doc-2.md").exists())
        finally:
            tmpdir.cleanup()

    @patch("handler.log_vram_usage")
    @patch("handler.run_orchestrated_cli")
    @patch("handler.VllmServerManager", _RecordingManager)
    @patch("handler.VllmWorker", _FakeVllmWorker)
    @patch("handler.extract_vllm_settings_from_job_input")
    def test_handler_enforces_handoff_before_postprocess(
        self,
        mock_extract_vllm_settings,
        mock_run_orchestrated_cli,
        mock_log_vram,
    ):
        del mock_log_vram
        mock_run_orchestrated_cli.side_effect = _mock_orchestrated_cli_success
        mock_extract_vllm_settings.return_value = SimpleNamespace(
            vllm_chunk_workers=1,
            vllm_block_correction_prompt="prompt",
            vllm_image_description_prompt="vision prompt",
        )

        tmpdir, root, _, _ = self._create_job_dirs()
        try:
            fake_config = _FakeConfig(root=root, use_postprocess_llm=True)
            job = {
                "input": {
                    "input_dir": "input",
                    "output_dir": "output",
                    "mineru_backend": "vlm-http-client",
                }
            }

            with patch("handler.setup_config", return_value=fake_config):
                result = handler.handler(job)

            self.assertEqual(result["status"], "completed")
            manager = _RecordingManager.instances[0]
            self.assertIn(("handoff", "mineru_parse", "notelm_postprocess", 5), manager.calls)
            self.assertIs(_FakeVllmWorker.instances[0].server_manager, manager)
        finally:
            tmpdir.cleanup()

    @patch("handler.log_vram_usage")
    @patch("handler.run_orchestrated_cli")
    @patch("handler.VllmServerManager", _RecordingManager)
    @patch("handler.VllmWorker", _FakeVllmWorker)
    @patch("handler.extract_vllm_settings_from_job_input")
    def test_parse_failure_stops_parse_server_and_blocks_postprocess(
        self,
        mock_extract_vllm_settings,
        mock_run_orchestrated_cli,
        mock_log_vram,
    ):
        del mock_log_vram
        mock_extract_vllm_settings.return_value = SimpleNamespace(
            vllm_chunk_workers=1,
            vllm_block_correction_prompt="prompt",
            vllm_image_description_prompt="vision prompt",
        )

        async def _fail_parse(**kwargs):
            del kwargs
            raise RuntimeError("parse failed")

        mock_run_orchestrated_cli.side_effect = _fail_parse

        tmpdir, root, _, _ = self._create_job_dirs()
        try:
            fake_config = _FakeConfig(root=root, use_postprocess_llm=True)
            job = {
                "input": {
                    "input_dir": "input",
                    "output_dir": "output",
                    "mineru_backend": "vlm-http-client",
                }
            }

            with patch("handler.setup_config", return_value=fake_config):
                with self.assertRaisesRegex(RuntimeError, "parse failed"):
                    handler.handler(job)

            manager_calls = _RecordingManager.instances[0].calls
            self.assertIn(("stop", "mineru_parse"), manager_calls)
            self.assertFalse(any(call[0] == "handoff" for call in manager_calls))
            self.assertTrue(all(not worker.entered for worker in _FakeVllmWorker.instances))
        finally:
            tmpdir.cleanup()

    @patch("handler.log_vram_usage")
    def test_handler_rejects_pipeline_backend_without_fallback(self, mock_log_vram):
        del mock_log_vram
        tmpdir, root, _, _ = self._create_job_dirs()
        try:
            fake_config = _FakeConfig(root=root, use_postprocess_llm=False)
            job = {
                "input": {
                    "input_dir": "input",
                    "output_dir": "output",
                    "mineru_backend": "pipeline",
                }
            }

            with patch("handler.setup_config", return_value=fake_config):
                with self.assertRaisesRegex(ValueError, "must be 'vlm-http-client'"):
                    handler.handler(job)
        finally:
            tmpdir.cleanup()


if __name__ == "__main__":
    unittest.main()
