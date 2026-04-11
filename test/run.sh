#!/bin/bash
# Copyright (C) 2026 withLambda
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

# Single-entry Docker validation workflow:
# - one image build
# - one container run
# - staged in-container validation with persisted host-visible results

set -euo pipefail

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
PROJECT_ROOT=$(dirname -- "${SCRIPT_DIR}")

BUILD_TEST_DIR="${PROJECT_ROOT}/build/test"
TEST_INPUT_DIR="${BUILD_TEST_DIR}/test-data/input"
TEST_OUTPUT_DIR="${BUILD_TEST_DIR}/test-data/output"
RESULTS_DIR="${BUILD_TEST_DIR}/results"
STAGES_DIR="${RESULTS_DIR}/stages"

DOCKER_IMAGE_NAME="${DOCKER_IMAGE_NAME:-notelm-migrate-validation}"
DOCKER_CONTAINER_NAME="${DOCKER_CONTAINER_NAME:-notelm-migrate-validation-run}"
VALIDATE_DEBUG_TRUE="${VALIDATE_DEBUG_TRUE:-0}"

write_build_failure_summary() {
  python3 - "${RESULTS_DIR}" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

def now() -> str:
    return datetime.now(timezone.utc).isoformat()

results_dir = Path(sys.argv[1])
summary = {
    "workflow": "docker-single-run-validation",
    "workflow_started_at": now(),
    "workflow_finished_at": now(),
    "final_exit_code": 1,
    "stage_order": [
        "build",
        "debug-deps-default",
        "deps",
        "cli-smoke",
        "server-readiness",
        "e2e-output",
        "runtime-assets",
        "debug-deps-true",
    ],
    "stages": [
        {
            "stage_id": "build",
            "description": "Build Docker image once",
            "status": "failed",
            "started_at": now(),
            "finished_at": now(),
            "duration_seconds": 0.0,
            "log": "stages/build.log",
            "details": {
                "reason": "docker_build_failed"
            }
        },
        {
            "stage_id": "debug-deps-default",
            "description": "Verify debug-gated dependency behavior with default DEBUG=false",
            "status": "skipped",
            "started_at": now(),
            "finished_at": now(),
            "duration_seconds": 0.0,
            "log": "stages/debug-deps-default.log",
            "details": {
                "reason": "build_failed"
            }
        },
        {
            "stage_id": "deps",
            "description": "Run runtime dependency sanity checks",
            "status": "skipped",
            "started_at": now(),
            "finished_at": now(),
            "duration_seconds": 0.0,
            "log": "stages/deps.log",
            "details": {
                "reason": "build_failed"
            }
        },
        {
            "stage_id": "cli-smoke",
            "description": "Run MinerU/vLLM CLI smoke checks",
            "status": "skipped",
            "started_at": now(),
            "finished_at": now(),
            "duration_seconds": 0.0,
            "log": "stages/cli-smoke.log",
            "details": {
                "reason": "build_failed"
            }
        },
        {
            "stage_id": "server-readiness",
            "description": "Start vLLM serving path and verify readiness endpoints",
            "status": "skipped",
            "started_at": now(),
            "finished_at": now(),
            "duration_seconds": 0.0,
            "log": "stages/server-readiness.log",
            "details": {
                "reason": "build_failed"
            }
        },
        {
            "stage_id": "e2e-output",
            "description": "Execute NoteLM handler sample flow and verify markdown output",
            "status": "skipped",
            "started_at": now(),
            "finished_at": now(),
            "duration_seconds": 0.0,
            "log": "stages/e2e-output.log",
            "details": {
                "reason": "build_failed"
            }
        },
        {
            "stage_id": "runtime-assets",
            "description": "Confirm required runtime model/assets are present",
            "status": "skipped",
            "started_at": now(),
            "finished_at": now(),
            "duration_seconds": 0.0,
            "log": "stages/runtime-assets.log",
            "details": {
                "reason": "build_failed"
            }
        },
        {
            "stage_id": "debug-deps-true",
            "description": "Optional DEBUG=true dependency check path",
            "status": "skipped",
            "started_at": now(),
            "finished_at": now(),
            "duration_seconds": 0.0,
            "log": "stages/debug-deps-true.log",
            "details": {
                "reason": "build_failed"
            }
        }
    ]
}

(results_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
PY
}

write_missing_summary_fallback() {
  local container_exit_code="$1"
  python3 - "${RESULTS_DIR}" "${container_exit_code}" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

def now() -> str:
    return datetime.now(timezone.utc).isoformat()

results_dir = Path(sys.argv[1])
container_exit_code = int(sys.argv[2])
summary = {
    "workflow": "docker-single-run-validation",
    "workflow_started_at": now(),
    "workflow_finished_at": now(),
    "final_exit_code": 1,
    "stage_order": [
        "debug-deps-default",
        "deps",
        "cli-smoke",
        "server-readiness",
        "e2e-output",
        "runtime-assets",
        "debug-deps-true",
    ],
    "stages": [
        {
            "stage_id": "debug-deps-default",
            "description": "Verify debug-gated dependency behavior with default DEBUG=false",
            "status": "failed",
            "started_at": now(),
            "finished_at": now(),
            "duration_seconds": 0.0,
            "log": "stages/container-run.log",
            "details": {
                "reason": "container_failed_before_summary",
                "container_exit_code": container_exit_code
            }
        },
        {
            "stage_id": "deps",
            "description": "Run runtime dependency sanity checks",
            "status": "skipped",
            "started_at": now(),
            "finished_at": now(),
            "duration_seconds": 0.0,
            "log": "stages/deps.log",
            "details": {
                "reason": "container_failed_before_summary"
            }
        },
        {
            "stage_id": "cli-smoke",
            "description": "Run MinerU/vLLM CLI smoke checks",
            "status": "skipped",
            "started_at": now(),
            "finished_at": now(),
            "duration_seconds": 0.0,
            "log": "stages/cli-smoke.log",
            "details": {
                "reason": "container_failed_before_summary"
            }
        },
        {
            "stage_id": "server-readiness",
            "description": "Start vLLM serving path and verify readiness endpoints",
            "status": "skipped",
            "started_at": now(),
            "finished_at": now(),
            "duration_seconds": 0.0,
            "log": "stages/server-readiness.log",
            "details": {
                "reason": "container_failed_before_summary"
            }
        },
        {
            "stage_id": "e2e-output",
            "description": "Execute NoteLM handler sample flow and verify markdown output",
            "status": "skipped",
            "started_at": now(),
            "finished_at": now(),
            "duration_seconds": 0.0,
            "log": "stages/e2e-output.log",
            "details": {
                "reason": "container_failed_before_summary"
            }
        },
        {
            "stage_id": "runtime-assets",
            "description": "Confirm required runtime model/assets are present",
            "status": "skipped",
            "started_at": now(),
            "finished_at": now(),
            "duration_seconds": 0.0,
            "log": "stages/runtime-assets.log",
            "details": {
                "reason": "container_failed_before_summary"
            }
        },
        {
            "stage_id": "debug-deps-true",
            "description": "Optional DEBUG=true dependency check path",
            "status": "skipped",
            "started_at": now(),
            "finished_at": now(),
            "duration_seconds": 0.0,
            "log": "stages/debug-deps-true.log",
            "details": {
                "reason": "container_failed_before_summary"
            }
        }
    ]
}

(results_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
PY
}

echo "Preparing build workspace at ${BUILD_TEST_DIR}"
rm -rf "${BUILD_TEST_DIR}"
mkdir -p "${TEST_INPUT_DIR}" "${TEST_OUTPUT_DIR}" "${STAGES_DIR}"

cp "${SCRIPT_DIR}"/*.txt \
  "${SCRIPT_DIR}"/*.py \
  "${SCRIPT_DIR}"/*.env \
  "${SCRIPT_DIR}/.dockerignore" \
  "${PROJECT_ROOT}/Dockerfile" \
  "${PROJECT_ROOT}/requirements.txt" \
  "${PROJECT_ROOT}/handler.py" \
  "${PROJECT_ROOT}/vllm_worker.py" \
  "${PROJECT_ROOT}/vllm_server.py" \
  "${PROJECT_ROOT}/utils.py" \
  "${PROJECT_ROOT}/settings.py" \
  "${PROJECT_ROOT}/check_dependencies.py" \
  "${PROJECT_ROOT}/debug_dependencies.py" \
  "${PROJECT_ROOT}/mineru.json" \
  "${PROJECT_ROOT}/block_correction_prompts.json" \
  "${BUILD_TEST_DIR}"

chmod -R a+rwx "${BUILD_TEST_DIR}/test-data" "${RESULTS_DIR}"

cd "${BUILD_TEST_DIR}" || exit 1

if ! python3 -c "import reportlab" >/dev/null 2>&1
then
  python3 -m pip install -r requirements-setup.txt
fi

echo "Generating sample PDFs into ${TEST_INPUT_DIR}"
python3 create-sample-pdfs.py

BUILD_LOG="${STAGES_DIR}/build.log"
CONTAINER_RUN_LOG="${STAGES_DIR}/container-run.log"

docker_build_cmd=(
  docker build
  -f Dockerfile
  -t "${DOCKER_IMAGE_NAME}"
  .
)

echo "Docker build command: ${docker_build_cmd[*]}"
if ! "${docker_build_cmd[@]}" 2>&1 | tee "${BUILD_LOG}"
then
  echo "Docker build failed. Writing summary artifact before exit."
  write_build_failure_summary
  exit 1
fi

docker_run_cmd=(
  docker run --rm
  --name "${DOCKER_CONTAINER_NAME}"
  --shm-size=4gb
  --env-file custom.env
  --env-file mineru.env
  --env-file tools.env
  -e STRICT_MODE=True
  -e DEBUG=false
  -e VALIDATE_DEBUG_TRUE="${VALIDATE_DEBUG_TRUE}"
  -e VALIDATION_RESULTS_DIR=/v/results
  -v "${PROJECT_ROOT}/models/huggingface:/v/huggingface-cache"
  -v "${PROJECT_ROOT}/models/datalab:/app/cache/datalab"
  -v "${TEST_INPUT_DIR}:/v/input"
  -v "${TEST_OUTPUT_DIR}:/v/output"
  -v "${RESULTS_DIR}:/v/results"
  "${DOCKER_IMAGE_NAME}"
  python3 -u docker_validation_workflow.py
)

echo "Docker run command: ${docker_run_cmd[*]}"
set +e
"${docker_run_cmd[@]}" 2>&1 | tee "${CONTAINER_RUN_LOG}"
CONTAINER_EXIT_CODE=${PIPESTATUS[0]}
set -e

if [ ! -f "${RESULTS_DIR}/summary.json" ]
then
  echo "Container ended without summary.json; writing fallback summary."
  write_missing_summary_fallback "${CONTAINER_EXIT_CODE}"
fi

echo "Validation results written to ${RESULTS_DIR}"
echo "Summary: ${RESULTS_DIR}/summary.json"

if [ "${CONTAINER_EXIT_CODE}" -ne 0 ]
then
  echo "Docker validation failed with exit code ${CONTAINER_EXIT_CODE}."
  exit "${CONTAINER_EXIT_CODE}"
fi

echo "Docker validation completed successfully."
