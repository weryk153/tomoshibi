#!/usr/bin/env python3
"""抓一輪新聞、更新主動開口的提示詞。給排程（cron）用的入口。

實作在 src/open_llm_vtuber/news_topics.py。這裡只是薄殼，讓舊的 cron 設定
（python scripts/news_topics.py）不必改就能繼續用。

平常不需要跑這支：設定頁的「主動話題」有立即更新的按鈕，而且 server 本身就有
定時任務。這支存在只為了在沒開 server 的時候也能更新。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.open_llm_vtuber.news_topics import refresh_from_news  # noqa: E402


def main() -> int:
    chars, new_titles = refresh_from_news()
    print(f"[news] wrote {chars} chars, {new_titles} new headline(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
