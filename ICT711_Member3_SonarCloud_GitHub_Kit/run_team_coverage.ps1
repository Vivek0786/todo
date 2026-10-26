<#
ICT711 Assessment 3 - Member 3 (coverage coordinator)
Runs ALL team test cases together under coverage.py and produces:
  - a terminal coverage report (saved to a log)
  - an HTML report in htmlcov\ (open htmlcov\index.html)
  - coverage.xml for import into SonarQube

Usage (from the GTD folder, virtual environment activated, .coveragerc present):
    powershell -ExecutionPolicy Bypass -File .\run_team_coverage.ps1 -TestLabels "member1_tests member2_tests member3_tests member4_tests"

Change -TestLabels to the real module/app names the team's tests live in.
#>
param(
    [string]$TestLabels = "member1_tests member2_tests member3_tests member4_tests"
)

$ErrorActionPreference = "Continue"
$evidence = "evidence\coverage"
New-Item -ItemType Directory -Force -Path $evidence | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$log = "$evidence\team_coverage_run_$stamp.txt"

if (-not (Test-Path ".coveragerc")) {
    Write-Host "ERROR: .coveragerc not found in this folder." -ForegroundColor Red
    exit 1
}

# Confirm which django-todo copy is being measured (must match what SonarQube scans).
"ICT711 team coverage run - $(Get-Date)" | Out-File $log -Encoding utf8
"Test labels: $TestLabels" | Out-File $log -Append -Encoding utf8
python -c "import todo, os; print('todo package measured at:', os.path.dirname(todo.__file__))" 2>&1 |
    Tee-Object -FilePath $log -Append

python -m coverage erase

Write-Host "Running all team tests under coverage..." -ForegroundColor Cyan
$labels = $TestLabels -split "\s+" | Where-Object { $_ -ne "" }
python -m coverage run manage.py test @labels -v 2 --durations 0 2>&1 |
    ForEach-Object { "$_" } | Tee-Object -FilePath $log -Append

"--- Coverage report ---" | Out-File $log -Append -Encoding utf8
python -m coverage report 2>&1 | ForEach-Object { "$_" } | Tee-Object -FilePath $log -Append
python -m coverage html
python -m coverage xml

Write-Host ""
Write-Host "Saved log:     $log" -ForegroundColor Green
Write-Host "HTML report:   htmlcov\index.html" -ForegroundColor Green
Write-Host "SonarQube XML: $(Resolve-Path coverage.xml)" -ForegroundColor Green
Write-Host "Copy that coverage.xml path into sonar-project.properties." -ForegroundColor Yellow
