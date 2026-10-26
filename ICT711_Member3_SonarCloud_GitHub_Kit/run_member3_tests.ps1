<#
ICT711 Assessment 3 - Member 3
Runs the four Member 3 automated cases (M3-01 to M3-04) plus the optional
exploratory check, prints per-test execution times, and saves a timestamped
copy of the output as evidence.

Usage (from the GTD folder, with the virtual environment activated):
    powershell -ExecutionPolicy Bypass -File .\run_member3_tests.ps1
#>

$ErrorActionPreference = "Continue"
$evidence = "evidence\member3"
New-Item -ItemType Directory -Force -Path $evidence | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$log = "$evidence\member3_test_run_$stamp.txt"

"ICT711 Member 3 automated test run - $(Get-Date)" | Out-File $log -Encoding utf8
"--- Environment ---" | Out-File $log -Append -Encoding utf8
python --version 2>&1 | Out-File $log -Append -Encoding utf8
python -c "import django; print('Django', django.get_version())" 2>&1 | Out-File $log -Append -Encoding utf8
python -m pip show django-todo 2>&1 | Select-String "^(Name|Version|Location|Editable)" | Out-File $log -Append -Encoding utf8
"--- Test output ---" | Out-File $log -Append -Encoding utf8

# 2>&1 merges Django's output (which goes to stderr) into the log.
# Expected on django-todo 2.7.0: M3-01, M3-03, M3-04 pass; M3-02 fails (genuine
# defect); the exploratory check fails (search page HTTP 500).
python manage.py test member3_tests -v 2 --durations 0 2>&1 |
    ForEach-Object { "$_" } | Tee-Object -FilePath $log -Append

Write-Host ""
Write-Host "Saved evidence log: $log" -ForegroundColor Green
