"""選用依賴缺少時，給出能照著做的錯誤訊息。

torch 放在 pyproject 的 `torch` extra 裡，而不是必裝：只有少數引擎用得到，
放必裝會讓每個人（包括桌面版首次啟動）多下載約 350MB。代價是選了那些引擎
卻沒裝時，原本的錯誤只有一句 "No module named 'torch'"，看不出該怎麼補。
"""

TORCH_EXTRA_HINT = (
    "This engine needs PyTorch, which is an optional dependency. "
    "Install it with: uv sync --extra torch"
)


def reraise_if_torch_missing(error: ModuleNotFoundError, engine: str) -> None:
    """缺的是 torch 就換成帶安裝指令的錯誤；缺別的照原樣往上拋。"""
    if error.name == "torch":
        raise ModuleNotFoundError(
            f"{engine}: {TORCH_EXTRA_HINT}", name="torch"
        ) from error
    raise error
