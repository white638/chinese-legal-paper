```powershell
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
$PythonCandidates = @($env:CLAUDE_PYTHON) + @((Get-Command python -ErrorAction SilentlyContinue).Source)
$Python = $null
foreach ($Candidate in $PythonCandidates | Select-Object -Unique) {
  if (-not $Candidate -or -not (Test-Path -LiteralPath $Candidate -PathType Leaf)) { continue }
  & $Candidate -B -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)"
  if ($LASTEXITCODE -eq 0) { $Python = $Candidate; break }
}
if (-not $Python) { throw 'Avereth requires Python 3.10 or newer.' }
$Controller = Join-Path $HOME '.claude\skills\cnki-paper\scripts\avereth.py'
& $Python -X utf8 $Controller doctor paper_rewriting_output
& $Python -X utf8 $Controller status paper_rewriting_output --json
& $Python -X utf8 $Controller plan paper_rewriting_output --json
```
