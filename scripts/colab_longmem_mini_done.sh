#!/bin/bash
# Second pass after run.sh: the five said-done items on the old engine (74ca83b),
# then all 30 items on the fix branch (440d824); both judged by the 27B.
# Ends with LONGMEM2_DONE (or LONGMEM2_FAILED) in /content/eval/run2.log.
set -euo pipefail
trap 'echo LONGMEM2_FAILED' ERR
B=b11609
L=/content/eval/llama
cudart=$(dirname "$(find "$L/cudart-llama-$B-bin-ubuntu-cuda-12.8-x64" -name 'libcudart*' | head -1)")
export LD_LIBRARY_PATH="/usr/lib64-nvidia:$cudart:$L/llama-$B"
OLD=/content/eval/host/out/2026-10-27-qwen9b-gguf-74ca83b-done
NEW=/content/eval/host/out/2026-10-27-qwen9b-gguf-fix440d824
NOTHINK='{"chat_template_kwargs":{"enable_thinking":false}}'

serve() {  # model alias port
  "$L/llama-$B/llama-server" -m "/content/eval/models/$1" --alias "$2" --host 127.0.0.1 --port "$3" \
    --ctx-size 16384 --parallel 2 --n-gpu-layers 99 --flash-attn on --jinja \
    --chat-template-kwargs '{"enable_thinking":false}' --reasoning-budget 0 --seed 12345 \
    > "/content/eval/server2-$3.log" 2>&1 &
  echo $! > "/content/eval/server2-$3.pid"
  for _ in $(seq 120); do curl -sf "http://127.0.0.1:$3/health" >/dev/null && return 0; sleep 5; done
  return 1
}

pkill -f llama-server || true; sleep 5
cd /content/eval/host
serve Qwen3.5-9B-Q4_K_M.gguf qwen/qwen3.5-9b 1234
pip install -q --force-reinstall --no-deps /content/eval/ai_character_engine-1.6.0-py3-none-any.whl
python scripts/run_longmem_mini.py --out "$OLD" --base-url http://127.0.0.1:1234/v1 \
  --model qwen/qwen3.5-9b --extra-body "$NOTHINK" --timeout 300 --only done-01,done-02,done-03,done-04,done-05
pip install -q --force-reinstall --no-deps /content/eval/fix/ai_character_engine-1.6.0-py3-none-any.whl
python scripts/run_longmem_mini.py --out "$NEW" --base-url http://127.0.0.1:1234/v1 \
  --model qwen/qwen3.5-9b --extra-body "$NOTHINK" --timeout 300
kill "$(cat /content/eval/server2-1234.pid)"; sleep 10

serve Qwen3.8-27B-UD-Q4_K_M.gguf qwen3.8-27b-ud-q4_k_m 18080
for out in "$OLD" "$NEW"; do
  python scripts/run_longmem_mini.py --out "$out" --judge-only \
    --judge-base-url http://127.0.0.1:18080/v1 --judge-model qwen3.8-27b-ud-q4_k_m
done
kill "$(cat /content/eval/server2-18080.pid)"
echo LONGMEM2_DONE
