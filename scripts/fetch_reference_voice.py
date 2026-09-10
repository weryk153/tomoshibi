#!/usr/bin/env python3
"""抓一段授權乾淨的日文參考音，給 GPT-SoVITS 當聲線用。

**為什麼是下載而不是隨附**

GPT-SoVITS 是 zero-shot 克隆：聲線完全由參考音決定，換檔案就換嗓子，不需要訓練。
所以「給角色一個聲音」等於「給它一段參考音」。

但大多數配音素材的「免費使用」不等於「可以隨專案再散布」。つくよみちゃんコーパス
的條款允許個人／法人、營利／非營利使用，也允許散布用它做出來的語音合成軟體——
但語料本身的再散布只在「原始發布消失且作者失聯」時才被允許。所以這支腳本讓你自己
從官方來源取得，而不是把檔案塞進 repo。

    https://tyc.rei-yumesaki.net/material/corpus/

本機自用不需要標示 credit；要公開發布用它合成的聲音，官方建議寫
「つくよみちゃんコーパス（CV.夢前黎）」。

**這支做什麼**

下載語料（約 493MB）、從 100 句錄音裡挑一段適合當參考音的、轉成 GPT-SoVITS 吃的
格式，連同逐字稿一起放到你的 references/ 資料夾。挑選規則不是隨機：

- 長度 7～10 秒。太短音色資訊不夠，太長沒必要。
- 片假名比例低。片假名多代表外來語與地名，音韻偏門，會把克隆出來的音色帶歪。

逐字稿會存成同名的 `.txt`。角色編輯器的參考音下拉會讀它，選了聲音就自動把逐字稿
一起填上——兩者是一組的，逐字稿給錯音色就會歪。

用法：
    python scripts/fetch_reference_voice.py <GPT-SoVITS 的 references 資料夾>
"""

import io
import os
import re
import subprocess
import sys
import urllib.request
import zipfile

CORPUS_URL = "https://tyc.rei-yumesaki.net/files/voice/tyc-corpus1.zip"
OUT_NAME = "tsukuyomi_ja"

MIN_SEC, MAX_SEC = 7.0, 10.0
MAX_KATAKANA_RATIO = 0.12
BYTES_PER_SEC = 96000 * 4          # 語料是 96kHz Float32 單聲道


def pick(z: zipfile.ZipFile):
    """回傳 (zip 成員名, 逐字稿)；挑不到回 None。"""
    scripts, members = {}, {}
    for zi in z.infolist():
        # 壓縮檔的檔名是 Shift-JIS，Python 會用 cp437 解讀，要轉回來
        name = zi.filename.encode("cp437").decode("cp932", errors="replace")
        if "補足なし台本" in name:
            for line in z.read(zi.filename).decode("utf-8", errors="replace").splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    scripts[k.strip()] = v.strip()
        elif name.endswith(".wav") and "01 WAV" in name:
            members[name.split("/")[-1][:-4]] = (zi.filename, zi.file_size)

    best = None
    for key, (member, size) in sorted(members.items()):
        sec = size / BYTES_PER_SEC
        text = scripts.get(key)
        if not text or not (MIN_SEC <= sec <= MAX_SEC):
            continue
        ratio = len(re.findall(r"[ァ-ヴー]", text)) / max(1, len(text))
        if ratio > MAX_KATAKANA_RATIO:
            continue
        # 片假名比例最低的優先；同分取較長的（音色資訊較多）
        score = (ratio, -sec)
        if best is None or score < best[0]:
            best = (score, member, text, key, sec)
    return best


def convert(src: str, dst: str) -> bool:
    """轉成 32kHz / 16-bit / 單聲道，對齊 GPT-SoVITS 的輸出格式。"""
    for cmd in (
        ["afconvert", "-f", "WAVE", "-d", "LEI16@32000", "-c", "1", src, dst],
        ["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-ar", "32000", "-ac", "1",
         "-sample_fmt", "s16", dst],
    ):
        try:
            subprocess.run(cmd, check=True)
            return True
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    return False


def main() -> int:
    if len(sys.argv) != 2:
        print("用法：python scripts/fetch_reference_voice.py <references 資料夾>",
              file=sys.stderr)
        return 2
    out_dir = sys.argv[1]
    if not os.path.isdir(out_dir):
        print(f"找不到資料夾：{out_dir}", file=sys.stderr)
        return 1

    print(f"下載語料（約 493MB，來源 {CORPUS_URL}）……")
    with urllib.request.urlopen(CORPUS_URL, timeout=600) as r:
        blob = r.read()
    print(f"  下載完成，{len(blob) // 1024 // 1024}MB")

    z = zipfile.ZipFile(io.BytesIO(blob))
    best = pick(z)
    if best is None:
        print("語料裡挑不到符合條件的片段（格式可能變了）", file=sys.stderr)
        return 1
    _score, member, text, key, sec = best
    print(f"  選用 {key}（{sec:.1f} 秒）")
    print(f"  逐字稿：{text}")

    raw = os.path.join(out_dir, f".{OUT_NAME}.raw.wav")
    with open(raw, "wb") as f:
        f.write(z.read(member))

    dst = os.path.join(out_dir, f"{OUT_NAME}.wav")
    ok = convert(raw, dst)
    os.remove(raw)
    if not ok:
        print("轉檔失敗：需要 afconvert（macOS 內建）或 ffmpeg", file=sys.stderr)
        return 1

    with open(os.path.join(out_dir, f"{OUT_NAME}.txt"), "w", encoding="utf-8") as f:
        f.write(text)

    print(f"\n完成：{dst}")
    print("到「設定 → 角色 → 編輯」的參考音下拉選它，逐字稿會自動填上。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
