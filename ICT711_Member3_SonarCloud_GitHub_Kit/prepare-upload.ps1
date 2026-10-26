<#
Run inside the extracted GitHub kit folder using WINDOWS PowerShell.
Adds actual source code from C:\ict711\django-todo\todo and transforms
existing coverage.xml from C:\ict711\gtd\coverage.xml to GitHub-compatible paths.
Does NOT require Docker, JDK, SonarScanner, or new Python packages.
Does NOT silently publish any data: user must inspect then commit/upload.
#>
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$source = 'C:\ict711\django-todo\todo'
$coverage = 'C:\ict711\gtd\coverage.xml'
if (!(Test-Path "$source\models.py")) { throw "Application folder missing: $source" }
if (!(Test-Path $coverage)) { throw "Coverage XML missing: $coverage" }
if (Test-Path "$here\todo") { Write-Host 'Refreshing existing todo copy' -ForegroundColor Yellow }
New-Item -ItemType Directory -Force -Path "$here\todo" | Out-Null

# Keep package code, templates and assets, but exclude bytecode and caches.
& robocopy.exe $source "$here\todo" /E /XD __pycache__ .git .venv venv /XF *.pyc *.pyo .env .env.* | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy failed, exit code $LASTEXITCODE" }
Write-Host 'App source copied to kit\todo' -ForegroundColor Green

$upstream = 'C:\ict711\django-todo'
foreach ($name in @('LICENSE','LICENSE.txt','LICENSE.md','COPYING','COPYING.txt','AUTHORS')) {
    if (Test-Path "$upstream\$name") { Copy-Item "$upstream\$name" "$here\$name" -Force }
}
try { $sha = (& git -C $upstream rev-parse HEAD 2>$null) } catch { $sha = 'not available' }
try { $origin = (& git -C $upstream remote get-url origin 2>$null) } catch { $origin = 'not available' }
@("Original application: django-todo 2.7.0 (verify using pip show)","Source repository: $origin","Commit: $sha","Imported locally on: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')") | Set-Content "$here\UPSTREAM_SOURCE.txt"

# Use the existing Python environment: no additional packages required.
$python = 'C:\ict711\venv\Scripts\python.exe'
if (!(Test-Path $python)) { $python = 'python' }
& $python "$here\normalize_coverage.py" $coverage "$here\coverage.xml"
if ($LASTEXITCODE -ne 0) { throw 'Coverage normalization failed; check source version and paths.' }

Write-Host 'DONE: inspect todo/, coverage.xml, UPSTREAM_SOURCE.txt, then edit sonar-project.properties.' -ForegroundColor Green
Write-Host 'Upload contents of this kit folder, not the outer ZIP itself.' -ForegroundColor Yellow
