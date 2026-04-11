import unittest
from pathlib import Path


class TestDockerValidationHarness(unittest.TestCase):
    def test_run_script_is_non_interactive_and_single_run(self):
        run_script = Path(__file__).resolve().parent / "run.sh"
        content = run_script.read_text(encoding="utf-8")

        self.assertNotIn("-it", content)
        self.assertEqual(content.count("docker build"), 1)
        self.assertEqual(content.count("docker run --rm"), 1)

    def test_run_script_mounts_results_and_uses_workflow_helper(self):
        run_script = Path(__file__).resolve().parent / "run.sh"
        content = run_script.read_text(encoding="utf-8")

        self.assertIn("-v \"${RESULTS_DIR}:/v/results\"", content)
        self.assertIn("python3 -u docker_validation_workflow.py", content)


if __name__ == "__main__":
    unittest.main()
