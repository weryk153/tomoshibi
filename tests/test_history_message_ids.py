"""get_history 回傳的每一則訊息都要有唯一的 id。

前端的 Message 型別把 id 標成必填，訊息列表也是用 key={msg.id} 渲染，但後端從來
沒送過這個欄位——每一則的 key 都是 undefined。初次載入時 React 只是掛載，重複的
key 頂多是警告；但要「替換一個已經有內容的列表」時（另一台裝置發話後把更新後的
紀錄推過來）reconciliation 會直接崩掉：

    NotFoundError: Failed to execute 'removeChild' on 'Node'

整個畫面變全白。所以 id 在讀取時就要補上——選在讀取而不是寫入，是因為既有的
歷史檔都沒有這個欄位，補在寫入端只能救新訊息，舊對話一樣會炸。
"""

import json

from src.open_llm_vtuber.chat_history_manager import get_history


def _write_history(tmp_path, conf_uid, history_uid, messages):
    d = tmp_path / "chat_history" / conf_uid
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{history_uid}.json").write_text(
        json.dumps(messages, ensure_ascii=False), encoding="utf-8"
    )


def test_every_message_has_an_id(tmp_path, monkeypatch):
    _write_history(
        tmp_path,
        "frieren",
        "hist-1",
        [
            {"role": "human", "content": "去哪", "timestamp": "2026-08-19T16:29:13"},
            {"role": "ai", "content": "往北。", "timestamp": "2026-08-19T16:29:53"},
        ],
    )
    monkeypatch.chdir(tmp_path)

    messages = get_history("frieren", "hist-1")

    assert all(m.get("id") for m in messages)


def test_ids_are_unique_even_when_content_and_timestamp_repeat(tmp_path, monkeypatch):
    # 同一秒內連送兩則一模一樣的訊息是做得到的（重複點送出、或主動發言重試）。
    # 用內容或時間當 id 會撞在一起，撞了就是同一個 React key，正是要避免的情況。
    _write_history(
        tmp_path,
        "frieren",
        "hist-1",
        [
            {"role": "ai", "content": "嗯。", "timestamp": "2026-08-19T16:29:13"},
            {"role": "ai", "content": "嗯。", "timestamp": "2026-08-19T16:29:13"},
            {"role": "ai", "content": "嗯。", "timestamp": "2026-08-19T16:29:13"},
        ],
    )
    monkeypatch.chdir(tmp_path)

    ids = [m["id"] for m in get_history("frieren", "hist-1")]

    assert len(set(ids)) == len(ids)


def test_ids_are_stable_across_reads(tmp_path, monkeypatch):
    # 每次讀都換一組 id 的話，推送過去等於整個列表全部換新，畫面會整片重繪、
    # 捲動位置也會跳掉。
    _write_history(
        tmp_path,
        "frieren",
        "hist-1",
        [
            {"role": "human", "content": "嗨", "timestamp": "2026-08-19T16:29:13"},
        ],
    )
    monkeypatch.chdir(tmp_path)

    assert [m["id"] for m in get_history("frieren", "hist-1")] == [
        m["id"] for m in get_history("frieren", "hist-1")
    ]


def test_existing_id_is_left_alone(tmp_path, monkeypatch):
    _write_history(
        tmp_path,
        "frieren",
        "hist-1",
        [
            {
                "role": "ai",
                "content": "嗨",
                "timestamp": "2026-08-19T16:29:13",
                "id": "keep-me",
            },
        ],
    )
    monkeypatch.chdir(tmp_path)

    assert get_history("frieren", "hist-1")[0]["id"] == "keep-me"


def test_metadata_entries_are_still_filtered_out(tmp_path, monkeypatch):
    _write_history(
        tmp_path,
        "frieren",
        "hist-1",
        [
            {"role": "metadata", "content": ""},
            {"role": "human", "content": "嗨", "timestamp": "2026-08-19T16:29:13"},
        ],
    )
    monkeypatch.chdir(tmp_path)

    messages = get_history("frieren", "hist-1")

    assert [m["role"] for m in messages] == ["human"]
