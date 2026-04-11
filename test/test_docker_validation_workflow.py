import json
import tempfile
import unittest
from pathlib import Path

from test import docker_validation_workflow as workflow


def _make_context(debug_true_enabled: bool = False) -> workflow.ValidationContext:
    temp_dir = Path(tempfile.mkdtemp())
    results_dir = temp_dir / "results"
    stages_dir = results_dir / "stages"
    output_dir = temp_dir / "output"
    input_dir = temp_dir / "input"
    stages_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    input_dir.mkdir(parents=True, exist_ok=True)

    return workflow.ValidationContext(
        results_dir=results_dir,
        stages_dir=stages_dir,
        input_dir=input_dir,
        output_dir=output_dir,
        debug_true_enabled=debug_true_enabled,
        readiness_timeout_seconds=1,
        readiness_poll_interval_seconds=0.01,
    )


class TestDockerValidationWorkflow(unittest.TestCase):
    def test_stage_specs_keep_stable_ids_and_optional_debug_true(self):
        context = _make_context(debug_true_enabled=False)
        stage_specs = workflow.build_stage_specs(context)

        self.assertEqual([stage.stage_id for stage in stage_specs], workflow.STABLE_STAGE_ORDER)
        debug_true_stage = stage_specs[-1]
        self.assertFalse(debug_true_stage.should_run)

    def test_execute_marks_remaining_stages_as_skipped_after_failure(self):
        context = _make_context()

        def failed_stage(_context: workflow.ValidationContext, _log_path: Path) -> tuple[bool, dict]:
            return False, {"reason": "intentional_failure"}

        def should_not_run(_context: workflow.ValidationContext, _log_path: Path) -> tuple[bool, dict]:
            raise AssertionError("This stage should have been skipped after earlier failure")

        stage_specs = [
            workflow.StageSpec("deps", "Deps", failed_stage),
            workflow.StageSpec("cli-smoke", "CLI", should_not_run),
            workflow.StageSpec("server-readiness", "Readiness", should_not_run),
        ]

        exit_code, records = workflow.execute_stage_specs(context, stage_specs)
        self.assertEqual(exit_code, 1)
        self.assertEqual([record["status"] for record in records], ["failed", "skipped", "skipped"])

    def test_write_summary_persists_expected_schema(self):
        context = _make_context()
        records = [
            {
                "stage_id": "deps",
                "description": "Run runtime dependency sanity checks",
                "status": "passed",
                "started_at": "2026-04-11T00:00:00+00:00",
                "finished_at": "2026-04-11T00:00:01+00:00",
                "duration_seconds": 1.0,
                "log": "stages/deps.log",
                "details": {},
            }
        ]

        workflow.write_summary(
            context,
            records,
            workflow_started_at="2026-04-11T00:00:00+00:00",
            final_exit_code=0,
        )

        summary_path = context.results_dir / "summary.json"
        payload = json.loads(summary_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["final_exit_code"], 0)
        self.assertIn("workflow_started_at", payload)
        self.assertIn("workflow_finished_at", payload)
        self.assertEqual(payload["stage_order"], workflow.STABLE_STAGE_ORDER)
        self.assertEqual(payload["stages"][0]["stage_id"], "deps")


if __name__ == "__main__":
    unittest.main()
