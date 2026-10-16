#!/usr/bin/env bash
# Runs every automated check and stores evidence in artifacts/qa/. Run from the project root
# with the virtual environment activated. Requires trained models and a built frontend for e2e.
set -u
mkdir -p artifacts/qa
status=0
python -m pytest tests/unit -q -p no:cacheprovider --junitxml=artifacts/qa/junit_unit.xml 2>&1 | tee artifacts/qa/log_unit.txt || status=1
python -m pytest tests/ml -q -p no:cacheprovider --junitxml=artifacts/qa/junit_ml.xml 2>&1 | tee artifacts/qa/log_ml.txt || status=1
python -m pytest tests/integration -q -p no:cacheprovider --junitxml=artifacts/qa/junit_integration.xml 2>&1 | tee artifacts/qa/log_integration.txt || status=1
(cd frontend && npx tsc --noEmit && npx vitest run --reporter=default --reporter=junit --outputFile.junit=../artifacts/qa/junit_frontend.xml) 2>&1 | tee artifacts/qa/log_frontend.txt || status=1
python -m pytest e2e -q -p no:cacheprovider --junitxml=artifacts/qa/junit_e2e.xml 2>&1 | tee artifacts/qa/log_e2e.txt || status=1
exit $status
