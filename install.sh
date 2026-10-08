#!/usr/bin/env bash
# Avereth / CNKI-Paper v7 dual-host installer for macOS, Linux, and Git Bash
set -euo pipefail

repo="$(cd "$(dirname "$0")" && pwd)"
avereth_host="codex"
runtime_home=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --host)
      [ "$#" -ge 2 ] || { echo "--host requires codex or claude" >&2; exit 2; }
      avereth_host="$2"
      shift 2
      ;;
    --runtime-home)
      [ "$#" -ge 2 ] || { echo "--runtime-home requires a path" >&2; exit 2; }
      runtime_home="$2"
      shift 2
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 2
      ;;
  esac
done
case "$avereth_host" in
  codex|claude) ;;
  *) echo "--host must be codex or claude" >&2; exit 2 ;;
esac

python_exe=""
if [ "$avereth_host" = "codex" ]; then
  profile_python="${CODEX_PYTHON:-}"
else
  profile_python="${CLAUDE_PYTHON:-}"
fi
for candidate in "$profile_python" \
  "$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3" \
  "$(command -v python3 2>/dev/null || true)" \
  "$(command -v python 2>/dev/null || true)"; do
  [ -n "$candidate" ] && [ -x "$candidate" ] || continue
  if "$candidate" -B -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)'; then
    python_exe="$candidate"
    break
  fi
done
[ -n "$python_exe" ] || { echo "Avereth v7 requires Python 3.10 or newer." >&2; exit 2; }

echo "== Avereth / CNKI-Paper v7 ($avereth_host) =="
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
install_args=(
  -B -X utf8 "$repo/tools/install_runtime.py"
  --host "$avereth_host"
  --repo-root "$repo"
  --json
)
if [ -n "$runtime_home" ]; then
  install_args+=(--runtime-home "$runtime_home")
fi
"$python_exe" "${install_args[@]}"

if [ "$avereth_host" = "codex" ]; then
  echo "Restart Codex, then ask for Avereth or invoke /prompts:avereth."
else
  echo "Restart Claude Code, then invoke /avereth."
fi
