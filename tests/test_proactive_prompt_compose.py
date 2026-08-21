"""主動發言提示詞的組裝：沒有話題清單時不要逼它硬找話題。

INSTRUCTION 裡固定寫著「想換題就從下面的主題或新聞挑一則」，但主題清單為空、
新聞也關閉時，下面什麼都沒有。再加上另一句「必須自己帶入一個新內容，不能把找
話題的責任丟回使用者」，模型被兩頭夾著：要從不存在的清單選題，又不准空手。結果
是自己編一句萬用問句丟回來。

實際看到的輸出：「……剛才那陣風有點大，讓樹葉沙沙響。費倫那時候好像想往西走，但被
修塔爾克擋了一下。我們就改往北了。你最近有聽過哪首曲子嗎？」——前半在延續場景，
結尾硬接一句不相干的問句。

沒有清單時，安靜地講一句當下的小事就夠了，不必製造話題。
"""

from src.open_llm_vtuber.news_topics import compose_content


PICK_FROM_LIST = "從下面的主題或新聞挑一則"


def test_no_topics_and_no_news_does_not_promise_a_list():
    content = compose_content(manual_topics=[], news_blocks=[], got_any=False)
    assert PICK_FROM_LIST not in content


def test_no_topics_says_it_is_fine_not_to_find_one():
    # 這是這次修正的重點：沒有清單時不要硬找話題。
    content = compose_content(manual_topics=[], news_blocks=[], got_any=False)
    assert "不必硬找話題" in content


def test_with_topics_the_list_hint_comes_back():
    content = compose_content(manual_topics=["科技"], news_blocks=[], got_any=False)
    assert PICK_FROM_LIST in content
    assert "科技" in content


def test_with_news_the_list_hint_comes_back():
    content = compose_content(
        manual_topics=[], news_blocks=["【某主題】\n- 一則新聞"], got_any=True
    )
    assert PICK_FROM_LIST in content


def test_the_guardrails_survive_in_every_case():
    # 「別像念稿」「一次只談一件事」這些護欄不管有沒有清單都必須在。
    for kwargs in (
        dict(manual_topics=[], news_blocks=[], got_any=False),
        dict(manual_topics=["科技"], news_blocks=[], got_any=False),
    ):
        content = compose_content(**kwargs)
        assert "不要像念稿" in content
        assert "一次只談一件事" in content


def test_generic_filler_questions_stay_banned_without_a_list():
    # 沒有清單不代表可以改用「最近有什麼新鮮事」這種問句填空。
    content = compose_content(manual_topics=[], news_blocks=[], got_any=False)
    assert "最近有什麼新鮮事" in content
