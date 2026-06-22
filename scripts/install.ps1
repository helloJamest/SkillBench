$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$RuntimeDir = Join-Path $Root "runtime"
$Target = if ($env:SKILLBENCH_HOME) { $env:SKILLBENCH_HOME } else { Join-Path $HOME ".skillbench" }
$Venv = Join-Path $Target "venv"

New-Item -ItemType Directory -Force -Path $Target | Out-Null
Set-Content -LiteralPath (Join-Path $Target "runtime.path") -Value $RuntimeDir
python -m venv $Venv
& (Join-Path $Venv "Scripts\python.exe") -m pip install --no-deps $Root
Write-Output "SkillBench runtime: $RuntimeDir"
Write-Output "SkillBench venv: $Venv"
Write-Output "Run: $(Join-Path $Venv 'Scripts\skillbench.exe')"
