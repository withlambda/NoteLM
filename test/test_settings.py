import os
import unittest

from pydantic import ValidationError

from settings import MinerUSettings


class TestMinerUSettings(unittest.TestCase):
    def setUp(self):
        # Set required env vars for GlobalConfig which might be instantiated
        os.environ["VOLUME_ROOT_MOUNT_PATH"] = "/tmp"
        os.environ["VRAM_GB_TOTAL"] = "24"

    def test_mineru_settings_defaults(self):
        settings = MinerUSettings()
        self.assertEqual(settings.backend, "vlm-http-client")
        self.assertEqual(settings.doc_language, "en")
        self.assertEqual(settings.ocr_mode, "auto")
        self.assertEqual(settings.output_format, "markdown")
        self.assertEqual(settings.server_url, "http://127.0.0.1:30000")
        self.assertEqual(settings.model_source, "local")
        self.assertEqual(settings.vl_model_name, "opendatalab/MinerU2.5-2509-1.2B")
        self.assertFalse(settings.disable_image_extraction)
        self.assertFalse(settings.debug)
        self.assertEqual(settings.vlm_host, "127.0.0.1")
        self.assertEqual(settings.vlm_port, 30000)
        self.assertEqual(settings.server_ready_check_retries, 2)
        self.assertEqual(settings.server_ready_check_delay, 2.0)

    def test_mineru_settings_server_url_defaults_from_host_port(self):
        settings = MinerUSettings(vlm_host="0.0.0.0", vlm_port=30123, server_url=None)
        self.assertEqual(settings.server_url, "http://0.0.0.0:30123")

    def test_mineru_settings_env_vars(self):
        os.environ["MINERU_SERVER_URL"] = "http://127.0.0.1:31000"
        os.environ["MINERU_DOC_LANGUAGE"] = "latin"
        os.environ["MINERU_OCR_MODE"] = "ocr"
        os.environ["MINERU_DEBUG"] = "True"
        os.environ["MINERU_VLM_READY_CHECK_RETRIES"] = "4"
        os.environ["MINERU_VLM_READY_CHECK_DELAY"] = "1.5"

        settings = MinerUSettings()
        self.assertEqual(settings.server_url, "http://127.0.0.1:31000")
        self.assertEqual(settings.doc_language, "latin")
        self.assertEqual(settings.ocr_mode, "ocr")
        self.assertTrue(settings.debug)
        self.assertEqual(settings.server_ready_check_retries, 4)
        self.assertEqual(settings.server_ready_check_delay, 1.5)

        # Cleanup
        del os.environ["MINERU_SERVER_URL"]
        del os.environ["MINERU_DOC_LANGUAGE"]
        del os.environ["MINERU_OCR_MODE"]
        del os.environ["MINERU_DEBUG"]
        del os.environ["MINERU_VLM_READY_CHECK_RETRIES"]
        del os.environ["MINERU_VLM_READY_CHECK_DELAY"]

    def test_mineru_settings_invalid_output_format(self):
        with self.assertRaises(ValidationError):
            MinerUSettings(output_format="json")

    def test_mineru_settings_extra_fields_ignored(self):
        # extra='ignore' should allow unknown fields without error
        settings = MinerUSettings(unknown_field="value")
        self.assertFalse(hasattr(settings, "unknown_field"))

if __name__ == "__main__":
    unittest.main()
