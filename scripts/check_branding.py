#!/usr/bin/env python3
"""發布前的品牌檢查：程式碼裡不准出現舊的專案名稱。

這個專案是 fork 來的，開發期間到處都是上一手的名字——檔名、註解、產生出來的
檔案。清乾淨之後還會回流：改了產生出來的提示詞卻沒改源頭，跑一次就全部回來；
搬動模組時把舊名字抄進新的 docstring。兩件事都真的發生過。

所以在發布流程裡放一道自動的關卡，而不是靠記得。

docs/ 不檢查：那是開發歷史，記錄了每個決定的理由，而且不隨程式碼發布。
"""

from __future__ import annotations

import subprocess
import sys

# 不可以出現在發布物裡的字串（不分大小寫）。
FORBIDDEN = ("warashi",)

# 排除的只有兩類：開發歷史（docs/superpowers/，不隨程式碼發布），以及守衛本身
# ——它必須寫得出那個字串才能檢查它。
#
# **docs/ 底下的使用者文件要檢查。** 早期這裡整個排除 docs/，結果三份使用者文件
# （GPT-SoVITS、遠端存取、加角色）裡的舊名稱一路活到打快照才被發現——守衛的範圍
# 比它宣稱的小，而它每次都回報通過。
EXCLUDED = (
    ":!docs/superpowers/",
    ":!*.lock",
    ":!scripts/check_branding.py",
    ":!frontend-src/scripts/check-i18n.mjs",
)


def offenders(needle: str) -> list[str]:
    result = subprocess.run(
        ["git", "grep", "-il", needle, "--", ".", *EXCLUDED],
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    failed = False
    for needle in FORBIDDEN:
        hits = offenders(needle)
        if hits:
            failed = True
            print(f"✗ 找到 {len(hits)} 個檔案還有 {needle!r}：")
            for path in hits:
                print(f"    {path}")
    if failed:
        print("\n這些必須清乾淨才能發布。理由見 docs/ 裡的 spec。")
        return 1
    print("✓ 品牌檢查通過：程式碼裡沒有舊名稱")
    return 0


if __name__ == "__main__":
    sys.exit(main())
