"""一鍵安裝 GPT-SoVITS：在自己電腦上合成語音，聲線由一段參考音決定。

內建的 Edge TTS 要連網，聲音也只有固定那幾種。GPT-SoVITS 在本機跑、換一段參考音就
換一副嗓子，但官方的安裝要自己開終端機、建 Python 環境、下載好幾個模型、改設定檔。
這裡把整串做完，進度用事件回報給前端，格式跟 ollama_installer 一樣。

裝在使用者資料夾（install_root），不在後端的工作目錄：桌面版更新時會整份覆寫程式
目錄，這包好幾 GB，不能跟著刪。

平台：
- macOS（Apple Silicon）：下載官方原始碼，用 uv 建 Python 3.10 環境裝依賴，模型另外
  下載。官方的依賴有三個要現場編譯（opencc 被指定從原始碼編、jieba_fast、
  pyopenjtalk），沒裝 Xcode Command Line Tools 的 Mac 會直接失敗，所以換成不必編譯
  的版本：opencc 用官方 wheel、pyopenjtalk 換成同介面的 pyopenjtalk-plus、jieba_fast
  換成原版 jieba 加一個同名的轉接模組（jieba_fast 是 jieba 的 C 加速版，介面相同）。
  torch 壓在 2.9 以下：之後的 torchaudio 讀音檔要另外裝 TorchCodec 和 FFmpeg，參考音
  一讀就回 400。
- Windows x64：官方整合包，Python、依賴、模型都在裡面（約 8.2GB），用 7-Zip 解壓。
其他平台不支援。

所有下載都釘死版本與 SHA-256：原始碼釘 tag 的封存檔，模型釘 Hugging Face 的 commit。
中斷的下載從斷點續傳——整合包 8GB，斷線就從頭來太折磨人。

參考音取自つくよみちゃんコーパス（CV.夢前黎）。條款允許用來做語音合成，但不允許隨
專案再散布語料，所以跟 scripts/fetch_reference_voice.py 一樣從官方來源取得。語料
493MB，只需要其中一句：用 HTTP Range 讀 zip 的目錄，只抓那一個檔案。

直接執行本模組會實際安裝一次、啟動並合成一句，給 CI 在乾淨的機器上驗證用：

    python -m src.open_llm_vtuber.gpt_sovits_installer
"""

import asyncio
import hashlib
import io
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator

import httpx
from loguru import logger

# 安裝位置可以覆寫。給 CI 與測試用，免得動到使用者真正的那一份。
DIR_ENV = "TOMOSHIBI_GPT_SOVITS_DIR"
# 桌面版把內附的 uv 路徑放在這裡；從原始碼跑的人用 PATH 上的 uv。
UV_ENV = "TOMOSHIBI_UV"

API_HOST = "127.0.0.1"
API_PORT = 9880
API_URL = f"http://{API_HOST}:{API_PORT}/tts"

MARKER = "installed.json"
SOURCE_TAG = "20250606v2pro"
WINDOWS_PACKAGE = "GPT-SoVITS-v2pro-20250604"
# macOS 依賴的每一個版本都釘死在這份清單（實際裝起來、合成過聲音的那一組）。
# GPT-SoVITS 的 requirements.txt 大多沒釘版本，解析器每次可能挑出不同的組合：
# 實測挑到 gradio 3.36.1 配 gradio_client 2.6.1，API 一啟動就 import 失敗。
MAC_CONSTRAINTS = Path(__file__).with_name("gpt_sovits_constraints_macos.txt")
MAC_REQUIREMENTS = "requirements.tomoshibi.txt"
WINDOWS_STAMP = ".tomoshibi-extracted"

# 參考音是日文錄音。要合成的文字是什麼語言另外設定（跨語言也能用，只是會帶口音）。
REFERENCE_LANG = "ja"
REFERENCE_NAME = "tsukuyomi_ja"
CORPUS_URL = "https://tyc.rei-yumesaki.net/files/voice/tyc-corpus1.zip"
REF_MIN_SEC, REF_MAX_SEC = 7.0, 10.0
REF_MAX_KATAKANA = 0.12
_CORPUS_BYTES_PER_SEC = 96000 * 4  # 語料是 96kHz Float32 單聲道

GB = 1000**3
# 大約的數字，給畫面顯示與事先檢查空間用。
MAC_PACKAGES_BYTES = 1_900_000_000
MAC_FREE_BYTES = 10 * GB
WINDOWS_FREE_BYTES = 30 * GB  # 8.2GB 的壓縮檔跟解壓出來的約 14GB 會同時存在（CI 實測）

START_TIMEOUT = 300.0  # 第一次載入模型要讀好幾百 MB
TEST_TIMEOUT = 600.0  # 第一次合成時 fast_langdetect 會先下載 134MB 的模型
DOWNLOAD_RETRIES = 5
PROGRESS_INTERVAL = 0.3

_HF_MODELS = "https://huggingface.co/lj1995/GPT-SoVITS/resolve/336b2ec4e8d4ac74740798dd40af44e74659ecaf"
_HF_EXTRAS = "https://huggingface.co/XXXXRT/GPT-SoVITS-Pretrained/resolve/0c47645e02a7bc3688d7b263b0042c81e3cd82cd"
_HF_WINDOWS = "https://huggingface.co/lj1995/GPT-SoVITS-windows-package/resolve/fb387b7a65a5441e5e3985f4ab9b721a9d455363"
_LEAKY_ENV = (
    "VIRTUAL_ENV",
    "UV_PROJECT_ENVIRONMENT",
    "PYTHONPATH",
    "PYTHONHOME",
    "CONDA_PREFIX",
)


class InstallError(Exception):
    """訊息會直接顯示給使用者。"""


@dataclass(frozen=True)
class Download:
    path: str  # 相對於 install_root
    url: str
    size: int
    sha256: str


def _model(name: str, size: int, sha256: str) -> Download:
    return Download(
        f"models/pretrained_models/{name}", f"{_HF_MODELS}/{name}", size, sha256
    )


MAC_DOWNLOADS = (
    Download(
        "downloads/source.zip",
        f"https://codeload.github.com/RVC-Boss/GPT-SoVITS/zip/refs/tags/{SOURCE_TAG}",
        6662521,
        "b6abce7c27c93e2c25c410254e785918ab17bc12169ca596d13dfefda04f70cf",
    ),
    _model(
        "chinese-hubert-base/config.json",
        1449,
        "c3e5060a1277e0f078cc6be9da4528a605dba6ece93018981fe2c820e5c7b103",
    ),
    _model(
        "chinese-hubert-base/preprocessor_config.json",
        212,
        "dcd684124d06722947939d41ea6ae58dbf10968c60a11a29f23ddc602c64a29b",
    ),
    _model(
        "chinese-hubert-base/pytorch_model.bin",
        188811417,
        "24164f129c66499d1346e2aa55f183250c223161ec2770c0da3d3b08cf432d3c",
    ),
    _model(
        "chinese-roberta-wwm-ext-large/config.json",
        963,
        "3d57de2fd7e80d0e5c8ff194f0bbb6baa10df7e43fc262a0cc71298a78b0a3e5",
    ),
    _model(
        "chinese-roberta-wwm-ext-large/pytorch_model.bin",
        651225145,
        "e53a693acc59ace251d143d068096ae0d7b79e4b1b503fa84c9dcf576448c1d8",
    ),
    _model(
        "chinese-roberta-wwm-ext-large/tokenizer.json",
        268962,
        "173796956820ea27bd14f76bf28162607ff4254807e2948253eb5b46f5bb643b",
    ),
    _model(
        "s1v3.ckpt",
        155284856,
        "87133414860ea14ff6620c483a3db5ed07b44be42e2c3fcdad65523a729a745a",
    ),
    _model(
        "v2Pro/s2Gv2Pro.pth",
        162303657,
        "0f8ead815234365edf045c6d86370ed6e4f440e8195be77ff0ea72684ad406a5",
    ),
    _model(
        "sv/pretrained_eres2netv2w24s4ep4.ckpt",
        107528697,
        "4f5a0bf73c61eb41b174e1bb54e7ee3c83233892be8e0af1f187024e8e581a35",
    ),
    Download(
        "downloads/G2PWModel.zip",
        f"{_HF_EXTRAS}/G2PWModel.zip",
        588856634,
        "46292be0374a49308069233cd5c147ae4c41806558e4781a2467a31a4d8099da",
    ),
    Download(
        "downloads/nltk_data.zip",
        f"{_HF_EXTRAS}/nltk_data.zip",
        9924448,
        "eb3ec26ace3f9ccbb08a6d333e26f0941c47e230ece0717dc992bdb7e99808dd",
    ),
)

WINDOWS_DOWNLOADS = (
    Download(
        "downloads/7zr.exe",
        "https://github.com/ip7z/7zip/releases/download/26.03/7zr.exe",
        602624,
        "ad4c82fadcbdf93c03b4fc440f300509c7d60c5c2f4d183e35d9d70d6957037d",
    ),
    Download(
        f"downloads/{WINDOWS_PACKAGE}.7z",
        f"{_HF_WINDOWS}/{WINDOWS_PACKAGE}.7z",
        8185086602,
        "bd60d0796553ff05d8568136e199c13e0dc22ebe2ed24273134e34ed6f215cd6",
    ),
)

# api_v2 的推論設定。只用 CPU：各種機器都跑得動，一句大約 2～9 秒。
TTS_INFER = """custom:
  bert_base_path: GPT_SoVITS/pretrained_models/chinese-roberta-wwm-ext-large
  cnhuhbert_base_path: GPT_SoVITS/pretrained_models/chinese-hubert-base
  device: cpu
  is_half: false
  t2s_weights_path: GPT_SoVITS/pretrained_models/s1v3.ckpt
  version: v2Pro
  vits_weights_path: GPT_SoVITS/pretrained_models/v2Pro/s2Gv2Pro.pth
"""

JIEBA_FAST_SHIM = {
    "__init__.py": (
        "# Tomoshibi：jieba_fast 是 jieba 的 C 加速版，介面相同。原版不必編譯，\n"
        "# 沒有 Xcode Command Line Tools 的 Mac 也裝得起來。\n"
        "from jieba import *  # noqa: F401,F403\n"
        "from jieba import setLogLevel  # noqa: F401\n"
    ),
    "posseg.py": "from jieba.posseg import *  # noqa: F401,F403\n",
}

# 用 GPT-SoVITS 自己環境裡的 librosa 轉檔，兩個平台都有，不必另外找 ffmpeg。
# 語料是 96kHz 的 32-bit float，轉成 32kHz／16-bit／單聲道。
_CONVERT_REFERENCE = (
    "import sys, librosa, soundfile; "
    "y, _ = librosa.load(sys.argv[1], sr=32000, mono=True); "
    "soundfile.write(sys.argv[2], y, 32000, subtype='PCM_16')"
)


def supported() -> bool:
    if sys.platform == "darwin":
        return platform.machine() == "arm64"
    if sys.platform == "win32":
        return platform.machine().upper() in ("AMD64", "X86_64")
    return False


def install_root() -> Path:
    override = os.environ.get(DIR_ENV)
    if override:
        return Path(override)
    if sys.platform == "win32":
        # 不放 Roaming：好幾 GB 的東西不該跟著漫遊設定檔同步。
        local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(local) / "Tomoshibi" / "GPT-SoVITS"
    if sys.platform == "darwin":
        return (
            Path.home() / "Library" / "Application Support" / "Tomoshibi" / "GPT-SoVITS"
        )
    return Path.home() / ".local" / "share" / "tomoshibi" / "gpt-sovits"


def tts_infer_path() -> Path:
    return install_root() / "tts_infer.yaml"


def download_bytes() -> int:
    if sys.platform == "win32":
        return sum(d.size for d in WINDOWS_DOWNLOADS)
    return sum(d.size for d in MAC_DOWNLOADS) + MAC_PACKAGES_BYTES


def required_free_bytes() -> int:
    return WINDOWS_FREE_BYTES if sys.platform == "win32" else MAC_FREE_BYTES


def read_marker() -> dict | None:
    """裝好了就回傳啟動資訊。沒裝、裝到一半、或檔案被刪掉都回 None。"""
    try:
        info = json.loads((install_root() / MARKER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(info, dict) or not Path(str(info.get("python", ""))).is_file():
        return None
    return info


def clean_env(**extra: str) -> dict:
    """子行程的環境變數。從啟用了 venv 的終端機開 app 時，這些會把 Python 指到別處。"""
    env = {k: v for k, v in os.environ.items() if k not in _LEAKY_ENV}
    env.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8", **extra)
    return env


def no_window() -> dict:
    """Windows 上別為每個子行程彈一個黑色主控台視窗。"""
    if sys.platform == "win32":
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    return {}


def mac_requirements(text: str) -> str:
    """把官方 requirements.txt 換成不必現場編譯的版本（理由見檔頭）。"""
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        name = (
            re.split(r"[<>=!~;\[\s]", stripped, maxsplit=1)[0].lower().replace("_", "-")
        )
        if stripped.startswith("--no-binary") or name in ("pyopenjtalk", "jieba-fast"):
            continue
        lines.append(line)
    lines += ["pyopenjtalk-plus", "jieba", "torch<2.9", "torchaudio<2.9"]
    return "\n".join(lines) + "\n"


def _zip_name(info: zipfile.ZipInfo) -> str:
    if info.flag_bits & 0x800:
        return info.filename
    # 語料的檔名是 Shift-JIS 但沒標 UTF-8 旗標，Python 會當成 cp437 解讀。
    try:
        return info.filename.encode("cp437").decode("cp932")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return info.filename


def pick_reference(z: zipfile.ZipFile) -> tuple[zipfile.ZipInfo, str] | None:
    """挑一句當參考音，規則同 scripts/fetch_reference_voice.py：7～10 秒、片假名少。"""
    scripts: dict[str, str] = {}
    wavs: dict[str, zipfile.ZipInfo] = {}
    for info in z.infolist():
        name = _zip_name(info)
        if "補足なし台本" in name:
            for line in z.read(info).decode("utf-8", errors="replace").splitlines():
                key, sep, text = line.partition(":")
                if sep:
                    scripts[key.strip()] = text.strip()
        elif name.endswith(".wav") and "01 WAV" in name:
            wavs[name.rsplit("/", 1)[-1][:-4]] = info

    best = None
    for key, info in sorted(wavs.items()):
        text = scripts.get(key)
        sec = info.file_size / _CORPUS_BYTES_PER_SEC
        if not text or not REF_MIN_SEC <= sec <= REF_MAX_SEC:
            continue
        ratio = len(re.findall(r"[ァ-ヴー]", text)) / max(1, len(text))
        if ratio > REF_MAX_KATAKANA:
            continue
        # 片假名比例最低的優先；同分取較長的（音色資訊較多）
        score = (ratio, -sec)
        if best is None or score < best[0]:
            best = (score, info, text)
    return None if best is None else (best[1], best[2])


class _RangeReader(io.RawIOBase):
    """把遠端檔案當成可以 seek 的本機檔案，每次讀取發一個 Range 請求。"""

    def __init__(self, client: httpx.Client, url: str):
        super().__init__()
        self._client, self._url, self._pos = client, url, 0
        head = client.head(url)
        head.raise_for_status()
        self.size = int(head.headers["content-length"])

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self._pos

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self._pos, io.SEEK_END: self.size}[whence]
        self._pos = base + offset
        return self._pos

    def readinto(self, buffer) -> int:
        if self._pos >= self.size:
            return 0
        end = min(self._pos + len(buffer), self.size) - 1
        resp = self._client.get(
            self._url, headers={"Range": f"bytes={self._pos}-{end}"}
        )
        if resp.status_code != 206:
            raise InstallError("Couldn't download the reference voice. Try again.")
        data = resp.content
        buffer[: len(data)] = data
        self._pos += len(data)
        return len(data)


class _Progress:
    def __init__(self, total: int):
        self.total, self.done, self._last = total, 0, 0.0

    def add(self, n: int) -> None:
        self.done += n

    def event(self, force: bool = False) -> dict | None:
        now = time.monotonic()
        if not force and now - self._last < PROGRESS_INTERVAL:
            return None
        self._last = now
        return {"status": "downloading", "completed": self.done, "total": self.total}


def _sha256(path: Path):
    digest = hashlib.sha256()
    if path.is_file():
        with open(path, "rb") as f:
            while chunk := f.read(1 << 20):
                digest.update(chunk)
    return digest


async def _fetch(
    client: httpx.AsyncClient, item: Download, root: Path, progress: _Progress
) -> AsyncIterator[dict]:
    """下載到 root/item.path 並驗 SHA-256。已經下載好的跳過，下載到一半的接著抓。"""
    dest = root / item.path
    if dest.is_file() and dest.stat().st_size == item.size:
        if (await asyncio.to_thread(_sha256, dest)).hexdigest() == item.sha256:
            progress.add(item.size)
            yield progress.event(force=True)
            return
        dest.unlink()

    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    have = part.stat().st_size if part.is_file() else 0
    if have > item.size:
        part.unlink()
        have = 0
    digest = await asyncio.to_thread(_sha256, part) if have else hashlib.sha256()
    progress.add(have)

    failures = 0
    while have < item.size:
        headers = {"Range": f"bytes={have}-"} if have else {}
        try:
            async with client.stream("GET", item.url, headers=headers) as resp:
                if have and resp.status_code == 200:
                    # 伺服器不支援續傳，只能從頭來。
                    progress.add(-have)
                    have, digest = 0, hashlib.sha256()
                resp.raise_for_status()
                with open(part, "ab" if have else "wb") as f:
                    async for chunk in resp.aiter_bytes(1 << 20):
                        f.write(chunk)
                        digest.update(chunk)
                        have += len(chunk)
                        progress.add(len(chunk))
                        failures = 0
                        event = progress.event()
                        if event:
                            yield event
            if have < item.size:
                raise httpx.RemoteProtocolError(
                    "connection closed before the download finished"
                )
        except httpx.TransportError as e:
            failures += 1
            if failures > DOWNLOAD_RETRIES:
                raise
            logger.info(
                f"[gpt-sovits] download interrupted ({type(e).__name__}); resuming at {have}"
            )
            await asyncio.sleep(min(2**failures, 30))

    if have != item.size or digest.hexdigest() != item.sha256:
        part.unlink(missing_ok=True)
        raise InstallError("A download didn't match its published checksum. Try again.")
    part.replace(dest)
    yield progress.event(force=True)


def _run(
    cmd: list[str],
    failure: str,
    *,
    timeout: float = 600,
    cwd: Path | None = None,
    env: dict | None = None,
) -> str:
    try:
        result = subprocess.run(
            cmd, capture_output=True, timeout=timeout, cwd=cwd, env=env, **no_window()
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        raise InstallError(f"{failure} ({type(e).__name__})") from e
    if result.returncode != 0:
        tail = (result.stderr or result.stdout or b"").decode(
            "utf-8", errors="replace"
        )[-2000:]
        logger.warning(
            f"[gpt-sovits] {Path(cmd[0]).name} exited {result.returncode}: {tail}"
        )
        raise InstallError(f"{failure} (exit {result.returncode})")
    return result.stdout.decode("utf-8", errors="replace")


def _find_uv() -> str:
    bundled = os.environ.get(UV_ENV)
    if bundled and Path(bundled).is_file():
        return bundled
    found = shutil.which("uv")
    if found:
        return found
    raise InstallError("Couldn't find uv, which is needed to set up GPT-SoVITS.")


def _replace_with_link(target: Path, link: Path) -> None:
    if link.is_symlink() or link.is_file():
        link.unlink()
    elif link.is_dir():
        shutil.rmtree(link)
    link.symlink_to(target, target_is_directory=True)


def _unpack_source(archive: Path, app: Path) -> None:
    staging = app.with_name("_source")
    shutil.rmtree(staging, ignore_errors=True)
    shutil.rmtree(app, ignore_errors=True)
    with zipfile.ZipFile(archive) as z:
        z.extractall(staging)
    tops = [p for p in staging.iterdir() if p.is_dir()]
    if len(tops) != 1 or not (tops[0] / "api_v2.py").is_file():
        raise InstallError("The GPT-SoVITS download didn't contain what we expected.")
    tops[0].replace(app)
    shutil.rmtree(staging, ignore_errors=True)


def _add_jieba_fast_shim(python: Path) -> None:
    purelib = _run(
        [
            str(python),
            "-c",
            "import sysconfig; print(sysconfig.get_paths()['purelib'])",
        ],
        "Couldn't finish setting up GPT-SoVITS's Python environment.",
        env=clean_env(),
    ).strip()
    package = Path(purelib) / "jieba_fast"
    package.mkdir(exist_ok=True)
    for name, body in JIEBA_FAST_SHIM.items():
        (package / name).write_text(body, encoding="utf-8")


def _arrange_mac_models(root: Path, app: Path) -> None:
    """模型放在 app 外面，用連結接進 GPT-SoVITS 寫死的位置。

    重裝時 app 會整個重建，模型不必跟著重新下載。
    """
    models = root / "models"
    for archive, top in (
        ("downloads/G2PWModel.zip", "G2PWModel"),
        ("downloads/nltk_data.zip", "nltk_data"),
    ):
        shutil.rmtree(models / top, ignore_errors=True)
        with zipfile.ZipFile(root / archive) as z:
            z.extractall(models)
    pretrained = models / "pretrained_models"
    # fast_langdetect 第一次用時把模型下載到這裡，資料夾不存在就直接失敗。
    (pretrained / "fast_langdetect").mkdir(parents=True, exist_ok=True)
    _replace_with_link(pretrained, app / "GPT_SoVITS" / "pretrained_models")
    _replace_with_link(models / "G2PWModel", app / "GPT_SoVITS" / "text" / "G2PWModel")


async def _install_mac(root: Path, uv: str) -> AsyncIterator[dict]:
    app = root / "app"
    yield {"status": "installing", "step": "packages"}
    await asyncio.to_thread(_unpack_source, root / "downloads" / "source.zip", app)
    requirements = (app / "requirements.txt").read_text(encoding="utf-8")
    (app / MAC_REQUIREMENTS).write_text(
        mac_requirements(requirements), encoding="utf-8"
    )
    env = clean_env(UV_PYTHON_PREFERENCE="only-managed")
    await asyncio.to_thread(
        _run,
        [uv, "venv", "--quiet", "--python", "3.10", str(app / ".venv")],
        "Couldn't create GPT-SoVITS's Python environment.",
        env=env,
    )
    python = app / ".venv" / "bin" / "python"
    await asyncio.to_thread(
        _run,
        [
            uv,
            "pip",
            "install",
            "--quiet",
            "--python",
            str(python),
            "--constraint",
            str(MAC_CONSTRAINTS),
            "-r",
            str(app / MAC_REQUIREMENTS),
        ],
        "Couldn't install GPT-SoVITS's Python packages. Check your connection and try again.",
        timeout=3600,
        env=env,
    )
    await asyncio.to_thread(_add_jieba_fast_shim, python)

    yield {"status": "installing", "step": "models"}
    await asyncio.to_thread(_arrange_mac_models, root, app)


def _windows_extracted(root: Path) -> bool:
    app = root / "app"
    try:
        stamp = (app / WINDOWS_STAMP).read_text(encoding="utf-8").strip()
    except OSError:
        return False
    return stamp == WINDOWS_PACKAGE and (app / "runtime" / "python.exe").is_file()


def _extract_7z(sevenzip: Path, archive: Path, dest: Path, state: dict) -> None:
    cmd = [str(sevenzip), "x", str(archive), f"-o{dest}", "-y", "-bsp1", "-bso0"]
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **no_window()
        )
    except OSError as e:
        raise InstallError("Couldn't unpack GPT-SoVITS.") from e
    tail = b""
    assert proc.stdout is not None
    while chunk := proc.stdout.read(512):
        tail = (tail + chunk)[-4000:]
        found = re.findall(rb"(\d{1,3})%", tail)
        if found:
            state["percent"] = min(100, int(found[-1]))
    if proc.wait() != 0:
        logger.warning(
            f"[gpt-sovits] 7zr failed: {tail.decode('utf-8', errors='replace')}"
        )
        raise InstallError(
            "Couldn't unpack GPT-SoVITS. Make sure there's enough disk space, then try again."
        )


async def _install_windows(root: Path) -> AsyncIterator[dict]:
    if _windows_extracted(root):
        return
    app, staging = root / "app", root / "_extract"
    sevenzip, archive = (root / d.path for d in WINDOWS_DOWNLOADS)
    await asyncio.to_thread(shutil.rmtree, staging, True)
    await asyncio.to_thread(shutil.rmtree, app, True)

    state = {"percent": 0}
    task = asyncio.ensure_future(
        asyncio.to_thread(_extract_7z, sevenzip, archive, staging, state)
    )
    while not task.done():
        yield {"status": "extracting", "percent": state["percent"]}
        await asyncio.wait({task}, timeout=2)
    task.result()

    tops = [p for p in staging.iterdir() if p.is_dir()]
    if len(tops) != 1 or not (tops[0] / "runtime" / "python.exe").is_file():
        raise InstallError("The GPT-SoVITS package didn't contain what we expected.")
    tops[0].replace(app)
    shutil.rmtree(staging, ignore_errors=True)
    (app / WINDOWS_STAMP).write_text(WINDOWS_PACKAGE, encoding="utf-8")
    # 解壓完壓縮檔就沒用了，先刪掉騰出 8GB。
    archive.unlink(missing_ok=True)


def _fetch_reference(root: Path, python: Path) -> dict:
    refs = root / "references"
    refs.mkdir(parents=True, exist_ok=True)
    wav, txt = refs / f"{REFERENCE_NAME}.wav", refs / f"{REFERENCE_NAME}.txt"
    if not (wav.is_file() and txt.is_file()):
        raw = refs / f".{REFERENCE_NAME}.raw.wav"
        timeout = httpx.Timeout(30.0, read=60.0)
        # 語料站偶爾連不上（CI 的 Windows 機器上遇過連線逾時）。連線失敗重試幾次；
        # 真的連不上就說清楚是哪裡，下載和解壓都留著，再按一次只補這一步。
        transport = httpx.HTTPTransport(retries=3)
        try:
            with httpx.Client(
                timeout=timeout, transport=transport, follow_redirects=True
            ) as client:
                reader = io.BufferedReader(_RangeReader(client, CORPUS_URL), 1 << 20)
                with zipfile.ZipFile(reader) as z:
                    picked = pick_reference(z)
                    if picked is None:
                        raise InstallError(
                            "Couldn't find a usable reference voice. Try again later."
                        )
                    info, text = picked
                    raw.write_bytes(z.read(info))  # zipfile 會驗 CRC
        except httpx.HTTPError as e:
            logger.warning(
                f"[gpt-sovits] reference download failed: {type(e).__name__}: {e}"
            )
            raise InstallError(
                "Couldn't reach the site the default voice comes from (tyc.rei-yumesaki.net). "
                "Try again in a little while — everything else is already downloaded."
            ) from e
        try:
            _run(
                [str(python), "-c", _CONVERT_REFERENCE, str(raw), str(wav)],
                "Couldn't prepare the reference voice.",
                env=clean_env(),
            )
        finally:
            raw.unlink(missing_ok=True)
        txt.write_text(text, encoding="utf-8")
    return {
        "path": str(wav),
        "prompt_text": txt.read_text(encoding="utf-8").strip(),
        "prompt_lang": REFERENCE_LANG,
    }


async def _synthesize_once(reference: dict) -> bool:
    params = {
        "text": "こんにちは。",
        "text_lang": REFERENCE_LANG,
        "ref_audio_path": reference["path"],
        "prompt_lang": reference["prompt_lang"],
        "prompt_text": reference["prompt_text"],
        "text_split_method": "cut5",
        "media_type": "wav",
    }
    try:
        async with httpx.AsyncClient(timeout=TEST_TIMEOUT) as client:
            resp = await client.get(API_URL, params=params)
    except httpx.HTTPError as e:
        logger.warning(f"[gpt-sovits] test synthesis failed: {type(e).__name__}: {e}")
        return False
    if resp.status_code != 200 or resp.content[:4] != b"RIFF":
        logger.warning(
            f"[gpt-sovits] test synthesis failed: HTTP {resp.status_code} {resp.text[:300]}"
        )
        return False
    return True


async def install(
    transport: httpx.AsyncBaseTransport | None = None,
) -> AsyncIterator[dict]:
    """依序回報 preparing → downloading（多次）→ installing／extracting → starting →
    testing → success。success 帶著參考音的路徑與逐字稿。失敗時丟 InstallError。"""
    if not supported():
        raise InstallError("One-click install isn't available on this system.")
    from . import gpt_sovits_service as service

    root = install_root()
    root.mkdir(parents=True, exist_ok=True)
    yield {"status": "preparing"}
    uv = _find_uv() if sys.platform == "darwin" else ""
    free = shutil.disk_usage(root).free
    if free < required_free_bytes():
        raise InstallError(
            f"Not enough disk space: GPT-SoVITS needs about {required_free_bytes() // GB} GB free "
            f"and there's {free // GB} GB."
        )
    # 重裝時先作廢舊的標記：裝到一半失敗，不能被當成已經裝好。
    (root / MARKER).unlink(missing_ok=True)
    service.stop()

    if sys.platform == "darwin":
        items = MAC_DOWNLOADS
    else:
        items = () if _windows_extracted(root) else WINDOWS_DOWNLOADS
    if items:
        # read 逾時就是「下載卡住」：一分鐘沒有任何資料進來就算這一次失敗，接著續傳。
        timeout = httpx.Timeout(30.0, read=60.0)
        async with httpx.AsyncClient(
            timeout=timeout, transport=transport, follow_redirects=True
        ) as client:
            progress = _Progress(sum(d.size for d in items))
            for item in items:
                async for event in _fetch(client, item, root, progress):
                    if event:
                        yield event

    if sys.platform == "darwin":
        async for event in _install_mac(root, uv):
            yield event
        app = root / "app"
        python, args = app / ".venv" / "bin" / "python", []
        env = {"NLTK_DATA": str(root / "models" / "nltk_data")}
    else:
        async for event in _install_windows(root):
            yield event
        app = root / "app"
        # 整合包的啟動腳本就是這樣跑的：-I 不讀使用者電腦上的 PYTHONPATH 與 site-packages。
        # 但 -I 也會忽略 PYTHONUTF8，stdout 導到檔案時就用 cp1252：api_v2 一印日文逐字稿
        # 就 UnicodeEncodeError，合成回 400（CI 實測）。-X utf8 是命令列參數，-I 擋不到。
        python, args, env = app / "runtime" / "python.exe", ["-I", "-X", "utf8"], {}

    yield {"status": "installing", "step": "voice"}
    tts_infer_path().write_text(TTS_INFER, encoding="utf-8")
    reference = await asyncio.to_thread(_fetch_reference, root, python)
    marker = {
        "version": WINDOWS_PACKAGE if sys.platform == "win32" else SOURCE_TAG,
        "app_dir": str(app),
        "python": str(python),
        "args": args,
        "env": env,
        "reference": reference,
    }
    (root / MARKER).write_text(
        json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    yield {"status": "starting"}
    started = await asyncio.to_thread(service.start) and await service.wait_ready(
        START_TIMEOUT
    )
    if started:
        yield {"status": "testing"}
    if not started or not await _synthesize_once(reference):
        service.stop()
        (root / MARKER).unlink(missing_ok=True)
        raise InstallError(
            "GPT-SoVITS was installed but couldn't make a sound. Try again."
        )

    await asyncio.to_thread(shutil.rmtree, root / "downloads", True)
    yield {"status": "success", "reference": reference}


async def _main() -> int:
    from . import gpt_sovits_service as service

    last_tick = -1
    try:
        async for event in install():
            if event["status"] in ("downloading", "extracting"):
                done = event.get("percent")
                if done is None:
                    done = event["completed"] * 100 // max(1, event["total"])
                if done // 5 == last_tick:
                    continue
                last_tick = done // 5
            print(json.dumps(event, ensure_ascii=False), flush=True)
    except (InstallError, httpx.HTTPError) as e:
        print(
            json.dumps({"status": "error", "error": str(e) or type(e).__name__}),
            flush=True,
        )
        return 1
    finally:
        service.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
