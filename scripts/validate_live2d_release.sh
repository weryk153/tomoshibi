#!/bin/sh
set -eu

# Read-only release checks. Deliberately do not expose CLI-Anything edit,
# migrate, flatten, or batch commands from this project wrapper.
repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
model=${1:-"$repo_root/live2d-models/kurisu_fan/kurisu.model3.json"}
python_bin="$repo_root/.venv/bin/python"
native_validator="$repo_root/skills/live2d-cubism-character-rig/scripts/validate_live2d_runtime.py"

if [ ! -f "$model" ]; then
  printf 'model not found: %s\n' "$model" >&2
  exit 2
fi

if [ ! -x "$python_bin" ]; then
  printf 'project Python not found: %s\n' "$python_bin" >&2
  exit 2
fi

if ! "$python_bin" -c 'import cli_anything.live2d' >/dev/null 2>&1; then
  printf '%s\n' 'CLI-Anything Live2D is not installed in the project environment.' >&2
  printf '%s\n' 'Pinned install:' >&2
  printf '%s\n' "  uv pip install --python .venv/bin/python 'git+https://github.com/HKUDS/CLI-Anything.git@39634a640cf20bc603b4faae4d31069c44821a9a#subdirectory=live2d/agent-harness'" >&2
  exit 2
fi

"$python_bin" "$native_validator" "$model"
"$python_bin" -m cli_anything.live2d.live2d_cli validate "$model" --strict
"$python_bin" -m cli_anything.live2d.live2d_cli runtime-check "$model" --target web-sdk
"$python_bin" -m cli_anything.live2d.live2d_cli manifest "$model"
