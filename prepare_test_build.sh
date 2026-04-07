#!/bin/bash
export SCRIPT_DIR="/Users/cb2lexe/Projects/github_repos/NoteLM/test"
export PARENT_OF_SCRIPT_DIR="/Users/cb2lexe/Projects/github_repos/NoteLM"
export BUILD_TEST_DIR="${PARENT_OF_SCRIPT_DIR}/build/test"
rm -rf "${BUILD_TEST_DIR}" && mkdir -p "${BUILD_TEST_DIR}"
cp "${SCRIPT_DIR}"/*.txt \
  "${SCRIPT_DIR}"/*.py \
  "${SCRIPT_DIR}"/*.env \
  "${SCRIPT_DIR}/.dockerignore" \
  "${PARENT_OF_SCRIPT_DIR}/Dockerfile" \
  "${PARENT_OF_SCRIPT_DIR}/requirements.txt" \
  "${PARENT_OF_SCRIPT_DIR}/handler.py" \
  "${PARENT_OF_SCRIPT_DIR}/vllm_worker.py" \
  "${PARENT_OF_SCRIPT_DIR}/utils.py" \
  "${PARENT_OF_SCRIPT_DIR}/settings.py" \
  "${PARENT_OF_SCRIPT_DIR}/check_dependencies.py" \
  "${PARENT_OF_SCRIPT_DIR}/block_correction_prompts.json" "${BUILD_TEST_DIR}"
cd "${BUILD_TEST_DIR}" && ls -F
