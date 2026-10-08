param(
    [ValidateSet("codex", "claude")]
    [string]$AverethHost = "codex",
    [string]$RuntimeHome = ""
)

# Avereth / CNKI-Paper v7 dual-host installer for Windows PowerShell
$ErrorActionPreference = "Stop"
$repo = $PSScriptRoot
$pythonCandidates = @()
if ($AverethHost -eq "codex" -and $env:CODEX_PYTHON) {
    $pythonCandidates += $env:CODEX_PYTHON
}
if ($AverethHost -eq "claude" -and $env:CLAUDE_PYTHON) {
    $pythonCandidates += $env:CLAUDE_PYTHON
}
$pythonCandidates += (Join-Path $HOME ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($pythonCommand) { $pythonCandidates += $pythonCommand.Source }
$pythonExe = $null
foreach ($candidate in $pythonCandidates | Select-Object -Unique) {
    if (-not $candidate -or -not (Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
    & $candidate -B -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)"
    if ($LASTEXITCODE -eq 0) { $pythonExe = $candidate; break }
}
if (-not $pythonExe) { throw "Avereth v7 requires Python 3.10 or newer." }

Write-Host "== Avereth / CNKI-Paper v7 ($AverethHost) =="
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$installArgs = @(
    "-B", "-X", "utf8",
    (Join-Path $repo "tools\install_runtime.py"),
    "--host", $AverethHost,
    "--repo-root", $repo,
    "--json"
)
if ($RuntimeHome) { $installArgs += @("--runtime-home", $RuntimeHome) }
& $pythonExe @installArgs
if ($LASTEXITCODE -ne 0) { throw "Avereth installation failed before acceptance." }

if ($AverethHost -eq "codex") {
    Write-Host "Restart Codex, then ask for Avereth or invoke /prompts:avereth."
} else {
    Write-Host "Restart Claude Code, then invoke /avereth."
}
