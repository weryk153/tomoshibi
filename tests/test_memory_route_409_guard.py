"""409 guard（「這段對話還沒連上」）抽成一個共用 helper。

原本三個端點（GET /api/memory、POST /api/memory、POST /api/memory/clear）各自
複製貼上同一段八行的 if-not-history_uid-409。跟 _resolved_uid 擺在一起收成
_resolved_history_uid，讓未來第四個需要「當前對話身分」的端點只要呼叫它、
不會複製貼上時漏掉這個檢查。

這裡直接測 helper 本身，釘住：
- 有連線時回 (history_uid, None)。
- 沒有連線時回 (None, 409 回應)，訊息文字跟原本一字不差——這一層不做在地化，
  照搬既有的中文字串是刻意的（api_guard / http.ts 同一個慣例）。
"""

import json
from types import SimpleNamespace

from src.open_llm_vtuber import memory_route

EXPECTED_MESSAGE = (
    "記憶現在屬於一段對話。請先在 app 裡連上這個角色，才知道要讀寫哪一段對話的記憶。"
)


def _ctx(conf_uid, history_uid):
    return SimpleNamespace(
        character_config=SimpleNamespace(conf_uid=conf_uid),
        history_uid=history_uid,
    )


def test_returns_the_history_uid_when_a_connection_exists():
    contexts = {"client-1": _ctx("charA", "conv9")}
    history_uid, bad = memory_route._resolved_history_uid(contexts, "charA")
    assert history_uid == "conv9"
    assert bad is None


def test_returns_409_with_the_original_message_when_no_connection_exists():
    history_uid, bad = memory_route._resolved_history_uid({}, "charA")
    assert history_uid is None
    assert bad is not None
    assert bad.status_code == 409
    body = json.loads(bytes(bad.body))
    assert body["error"] == EXPECTED_MESSAGE


def test_a_connection_still_initialising_triggers_the_409():
    contexts = {"client-1": _ctx("charA", "")}
    history_uid, bad = memory_route._resolved_history_uid(contexts, "charA")
    assert history_uid is None
    assert bad.status_code == 409
