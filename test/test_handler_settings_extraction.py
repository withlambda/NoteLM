import unittest
from unittest.mock import patch
import sys
from pathlib import Path

# Ensure the project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Tests rely on real project dependencies; `conftest.py` intentionally avoids shims.
from handler import extract_mineru_settings_from_job_input
from settings import MinerUSettings

class TestMinerUSettingsExtraction(unittest.TestCase):
    def test_extract_valid_overrides(self):
        job_input = {
            "doc_language": "latin",
            "mineru_backend": "vlm-http-client",
            "mineru_ocr_mode": "ocr",
            "mineru_api_url": "http://127.0.0.1:8080",
            "mineru_server_url": "http://127.0.0.1:30000",
            "mineru_model_source": "local",
            "mineru_vl_model_name": "custom/mineru-model",
            "mineru_debug": True,
            "output_format": "markdown"
        }
        settings = extract_mineru_settings_from_job_input(job_input)
        self.assertIsInstance(settings, MinerUSettings)
        self.assertEqual(settings.backend, "vlm-http-client")
        self.assertEqual(settings.doc_language, "latin")
        self.assertEqual(settings.ocr_mode, "ocr")
        self.assertEqual(settings.api_url, "http://127.0.0.1:8080")
        self.assertEqual(settings.server_url, "http://127.0.0.1:30000")
        self.assertEqual(settings.model_source, "local")
        self.assertEqual(settings.vl_model_name, "custom/mineru-model")
        self.assertTrue(settings.debug)
        self.assertEqual(settings.output_format, "markdown")

    def test_extract_empty_input_uses_defaults(self):
        job_input = {}
        settings = extract_mineru_settings_from_job_input(job_input)
        # Defaults from MinerUSettings
        self.assertEqual(settings.backend, "vlm-http-client")
        self.assertEqual(settings.doc_language, "en")
        self.assertEqual(settings.ocr_mode, "auto")
        self.assertEqual(settings.output_format, "markdown")
        self.assertEqual(settings.model_source, "local")
        self.assertIsNone(settings.api_url)
        self.assertEqual(settings.server_url, "http://127.0.0.1:30000")

    def test_extract_api_url_and_server_url_are_distinct(self):
        job_input = {
            "mineru_api_url": "http://127.0.0.1:18080",
            "mineru_server_url": "http://127.0.0.1:30001",
            "mineru_model_source": "local",
            "mineru_vl_model_name": "opendatalab/MinerU2.5-2509-1.2B",
        }
        settings = extract_mineru_settings_from_job_input(job_input)
        self.assertEqual(settings.api_url, "http://127.0.0.1:18080")
        self.assertEqual(settings.server_url, "http://127.0.0.1:30001")
        self.assertEqual(settings.model_source, "local")
        self.assertEqual(settings.vl_model_name, "opendatalab/MinerU2.5-2509-1.2B")

    def test_extract_unknown_keys_warns_but_ignores(self):
        job_input = {
            "mineru_unknown_field": "value",
            "some_other_key": "ignore"
        }
        with patch("handler.logger.warning") as mock_warn:
            settings = extract_mineru_settings_from_job_input(job_input)
            mock_warn.assert_called_once()
            self.assertIn("Unknown mineru setting 'mineru_unknown_field'", mock_warn.call_args[0][0])

        # Verify it's not on the object
        self.assertFalse(hasattr(settings, "unknown_field"))

    def test_extract_mineru_specific_fields(self):
        job_input = {
            "mineru_page_range": "1-5",
            "mineru_disable_image_extraction": True,
            "mineru_server_ready_check_retries": 5,
            "mineru_server_ready_check_delay": 0.25,
        }
        settings = extract_mineru_settings_from_job_input(job_input)
        self.assertEqual(settings.page_range, "1-5")
        self.assertTrue(settings.disable_image_extraction)
        self.assertEqual(settings.server_ready_check_retries, 5)
        self.assertEqual(settings.server_ready_check_delay, 0.25)

    def test_extract_mixed_input(self):
        job_input = {
            "mineru_vlm_port": 31000,
            "vllm_model_path": "/some/path", # Should be ignored by MinerU extractor
            "other": "value"
        }
        settings = extract_mineru_settings_from_job_input(job_input)
        self.assertEqual(settings.vlm_port, 31000)

if __name__ == "__main__":
    unittest.main()
