#!/bin/bash
# Mini long-memory benchmark on a Colab L4: Qwen3.5-9B answers, Qwen3.8-27B judges.
# Ends with LONGMEM_DONE (or LONGMEM_FAILED) in /content/eval/run.log.
set -euo pipefail
cd /content/eval
B=b11609
L=/content/eval/llama
OUT=/content/eval/host/out/2026-10-27-qwen9b-gguf-main74ca83b
trap 'echo LONGMEM_FAILED' ERR

if [ ! -x "$L/llama-$B/llama-server" ]; then
  for a in llama-$B-bin-ubuntu-cuda-12.8-x64 cudart-llama-$B-bin-ubuntu-cuda-12.8-x64; do
    curl -sL -o "$L/$a.tar.gz" "https://github.com/ggml-org/llama.cpp/releases/download/$B/$a.tar.gz"
    mkdir -p "$L/$a" && tar -xzf "$L/$a.tar.gz" -C "$L/$a"
  done
  # The release tarball nests its binaries one level down; flatten to llama-$B.
  srv=$(find "$L/llama-$B-bin-ubuntu-cuda-12.8-x64" -name llama-server -type f | head -1)
  ln -sfn "$(dirname "$srv")" "$L/llama-$B"
fi
cudart=$(dirname "$(find "$L/cudart-llama-$B-bin-ubuntu-cuda-12.8-x64" -name 'libcudart*' | head -1)")
export LD_LIBRARY_PATH="/usr/lib64-nvidia:$cudart:$L/llama-$B"

python - <<'EOF'
from huggingface_hub import hf_hub_download
hf_hub_download("lmstudio-community/Qwen3.5-9B-GGUF", "Qwen3.5-9B-Q4_K_M.gguf",
                revision="1379f25c6b505a3fc737bd7818cb09389cf807c1", local_dir="/content/eval/models")
hf_hub_download("unsloth/Qwen3.8-27B-GGUF", "Qwen3.8-27B-UD-Q4_K_M.gguf",
                revision="4ca720788d1e01f1bff70c033e0d0028fd02e502", local_dir="/content/eval/models")
EOF
pip install -q /content/eval/ai_character_engine-1.6.0-py3-none-any.whl

serve() {  # model alias port
  "$L/llama-$B/llama-server" -m "/content/eval/models/$1" --alias "$2" --host 127.0.0.1 --port "$3" \
    --ctx-size 16384 --parallel 2 --n-gpu-layers 99 --flash-attn on --jinja \
    --chat-template-kwargs '{"enable_thinking":false}' --reasoning-budget 0 --seed 12345 \
    > "/content/eval/server-$3.log" 2>&1 &
  echo $! > "/content/eval/server-$3.pid"
  for _ in $(seq 120); do curl -sf "http://127.0.0.1:$3/health" >/dev/null && return 0; sleep 5; done
  return 1
}

cd /content/eval/host
NOTHINK='{"chat_template_kwargs":{"enable_thinking":false}}'
serve Qwen3.5-9B-Q4_K_M.gguf qwen/qwen3.5-9b 1234
python scripts/run_longmem_mini.py --out "$OUT" --base-url http://127.0.0.1:1234/v1 \
  --model qwen/qwen3.5-9b --extra-body "$NOTHINK"
kill "$(cat /content/eval/server-1234.pid)"; sleep 10

serve Qwen3.8-27B-UD-Q4_K_M.gguf qwen3.8-27b-ud-q4_k_m 18080
python scripts/run_longmem_mini.py --out "$OUT" --judge-only \
  --judge-base-url http://127.0.0.1:18080/v1 --judge-model qwen3.8-27b-ud-q4_k_m
kill "$(cat /content/eval/server-18080.pid)"
echo LONGMEM_DONE
