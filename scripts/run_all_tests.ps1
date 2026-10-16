# Windows PowerShell equivalent of run_all_tests.sh. Run from the project root with the venv activated.
New-Item -ItemType Directory -Force artifacts\qa | Out-Null
$failed = $false
python -m pytest tests/unit -q -p no:cacheprovider --junitxml=artifacts/qa/junit_unit.xml 2>&1 | Tee-Object artifacts/qa/log_unit.txt; if ($LASTEXITCODE) { $failed = $true }
python -m pytest tests/ml -q -p no:cacheprovider --junitxml=artifacts/qa/junit_ml.xml 2>&1 | Tee-Object artifacts/qa/log_ml.txt; if ($LASTEXITCODE) { $failed = $true }
python -m pytest tests/integration -q -p no:cacheprovider --junitxml=artifacts/qa/junit_integration.xml 2>&1 | Tee-Object artifacts/qa/log_integration.txt; if ($LASTEXITCODE) { $failed = $true }
Push-Location frontend
npx tsc --noEmit; if ($LASTEXITCODE) { $failed = $true }
npx vitest run --reporter=default --reporter=junit --outputFile.junit=../artifacts/qa/junit_frontend.xml 2>&1 | Tee-Object ../artifacts/qa/log_frontend.txt; if ($LASTEXITCODE) { $failed = $true }
Pop-Location
python -m pytest e2e -q -p no:cacheprovider --junitxml=artifacts/qa/junit_e2e.xml 2>&1 | Tee-Object artifacts/qa/log_e2e.txt; if ($LASTEXITCODE) { $failed = $true }
if ($failed) { exit 1 }
