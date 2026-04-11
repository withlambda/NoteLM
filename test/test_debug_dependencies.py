import os
import unittest
from unittest.mock import patch

from debug_dependencies import is_debug_enabled, run_debug_dependency_check_if_enabled


class TestDebugDependencies(unittest.TestCase):
    def test_is_debug_enabled_defaults_to_false(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(is_debug_enabled())

    def test_is_debug_enabled_accepts_truthy_values(self):
        for value in ["1", "true", "TRUE", "yes", "on"]:
            with patch.dict(os.environ, {"DEBUG": value}, clear=True):
                self.assertTrue(is_debug_enabled())

    def test_run_debug_dependency_check_if_enabled_runs_check(self):
        with patch.dict(os.environ, {"DEBUG": "true"}, clear=True):
            with patch("check_dependencies.main") as mock_check:
                run_debug_dependency_check_if_enabled()
                mock_check.assert_called_once()

    def test_run_debug_dependency_check_if_enabled_skips_when_disabled(self):
        with patch.dict(os.environ, {"DEBUG": "false"}, clear=True):
            with patch("check_dependencies.main") as mock_check:
                run_debug_dependency_check_if_enabled()
                mock_check.assert_not_called()


if __name__ == "__main__":
    unittest.main()
