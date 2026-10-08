$BundledPython = Join-Path $HOME '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$PythonCandidates = @($env:CODEX_PYTHON, $BundledPython) + @(
