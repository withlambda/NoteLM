import unittest
from unittest.mock import call, patch

import check_dependencies


class TestCheckDependencies(unittest.TestCase):
    def _run_main_with_exit_capture(self) -> int:
        with patch(
            "check_dependencies.sys.exit",
            side_effect=lambda code=0: (_ for _ in ()).throw(SystemExit(code)),
        ) as mock_exit:
            with self.assertRaises(SystemExit) as raised:
                check_dependencies.main()
        self.assertEqual(mock_exit.call_count, 1)
        return raised.exception.code

    def test_main_succeeds_with_expected_dependency_contract(self):
        with patch("check_dependencies.check_import", return_value=True) as mock_check_import:
            with patch("check_dependencies.check_vllm_entrypoint", return_value=True) as mock_entrypoint:
                with patch("check_dependencies.run_command_check", return_value=True):
                    exit_code = self._run_main_with_exit_capture()

        self.assertEqual(exit_code, 0)
        self.assertIn(call("vllm"), mock_check_import.call_args_list)
        self.assertNotIn(call("paddle"), mock_check_import.call_args_list)
        self.assertNotIn(call("cuda"), mock_check_import.call_args_list)
        self.assertNotIn(call("shapely"), mock_check_import.call_args_list)
        mock_entrypoint.assert_called_once()

    def test_main_fails_when_vllm_is_not_importable(self):
        def import_side_effect(module_name: str) -> bool:
            return module_name != "vllm"

        with patch("check_dependencies.check_import", side_effect=import_side_effect):
            with patch("check_dependencies.check_vllm_entrypoint", return_value=True) as mock_entrypoint:
                with patch("check_dependencies.run_command_check", return_value=True):
                    exit_code = self._run_main_with_exit_capture()

        self.assertEqual(exit_code, 1)
        mock_entrypoint.assert_not_called()

    def test_main_runs_lightweight_and_bounded_command_checks(self):
        with patch("check_dependencies.check_import", return_value=True):
            with patch("check_dependencies.check_vllm_entrypoint", return_value=True):
                with patch("check_dependencies.run_command_check", return_value=True) as mock_run_command_check:
                    exit_code = self._run_main_with_exit_capture()

        self.assertEqual(exit_code, 0)
        self.assertEqual(mock_run_command_check.call_count, 5)

        served_model_smoke_check = call(
            [
                "python3",
                "-m",
                "mineru.cli.vlm_server",
                "--served-model-name",
                "opendatalab/MinerU2.5-2509-1.2B",
                "--help",
            ],
            "MinerU vLLM served-model-name wiring smoke check",
        )
        self.assertIn(served_model_smoke_check, mock_run_command_check.call_args_list)


if __name__ == "__main__":
    unittest.main()
