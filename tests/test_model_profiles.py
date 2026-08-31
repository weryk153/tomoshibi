"""arch → 偵測不到的必要設定。

界線：profile 只放偵測得不到的怪癖。is_vlm / supports_tools / max_context 都是
probe 直接回的，不進這個檔。

注意 extra_body 底下同時住著必要設定（reasoning_effort）與 sampling 旋鈕
（top_p / presence_penalty）。這個檔只准放前者。分界不靠欄位名，靠 note 寫不
寫得出來：能說出「不設會出現什麼故障」的才算必要設定。note 必填就是這條規則的
機械化——載入時檢查，缺 note 的項目不收。
"""

from src.open_llm_vtuber import model_profiles as mp
from src.open_llm_vtuber.model_probe import DetectedModel


def _model(**kw):
    base = dict(id="m", backend="lmstudio", base_url="http://x/v1")
    base.update(kw)
    return DetectedModel(**base)


PROFILES = [
    {
        "match_arch": ["qwen35", "qwen3"],
        "match_backend": "lmstudio",
        "extra_body": {"reasoning_effort": "none"},
        "note": "不關思考模式會超過 60 秒 timeout，然後靜默 fallback。",
    },
    {
        "match_arch": ["madeup"],
        "extra_body": {"foo": "bar"},
        "note": "測試用：沒有 match_backend 代表不限後端。",
    },
]


def test_matches_by_arch_and_backend():
    p = mp.profile_for(_model(arch="qwen35", backend="lmstudio"), PROFILES)
    assert p["extra_body"] == {"reasoning_effort": "none"}
    assert "timeout" in p["note"]


def test_any_arch_in_the_list_counts():
    assert mp.profile_for(_model(arch="qwen3", backend="lmstudio"), PROFILES) is not None


def test_backend_mismatch_does_not_match():
    assert mp.profile_for(_model(arch="qwen35", backend="ollama"), PROFILES) is None


def test_omitted_match_backend_means_any_backend():
    assert mp.profile_for(_model(arch="madeup", backend="ollama"), PROFILES) is not None


def test_unknown_arch_returns_none():
    """查不到就什麼都不寫。不猜、不套通用建議值。"""
    assert mp.profile_for(_model(arch="llama"), PROFILES) is None


def test_no_arch_returns_none():
    assert mp.profile_for(_model(arch=None), PROFILES) is None


def test_matches_unnormalized_mixed_case_profiles():
    """profile_for 對未經 normalize() 的輸入也要成立——match_backend 跟
    match_arch 一樣都要在這裡自己 lower，不能只信任已正規化的資料。"""
    unnormalized = [
        {
            "match_arch": ["QWEN35"],
            "match_backend": "LMStudio",
            "extra_body": {"reasoning_effort": "none"},
            "note": "混合大小寫，未過 normalize()。",
        }
    ]
    p = mp.profile_for(_model(arch="qwen35", backend="lmstudio"), unnormalized)
    assert p is not None
    assert p["extra_body"] == {"reasoning_effort": "none"}


def test_first_match_wins_and_warns(caplog):
    dupes = [
        {"match_arch": ["x"], "extra_body": {"a": "1"}, "note": "第一條"},
        {"match_arch": ["x"], "extra_body": {"a": "2"}, "note": "第二條"},
    ]
    p = mp.profile_for(_model(arch="x"), dupes)
    assert p["extra_body"] == {"a": "1"}


def test_entries_without_note_are_dropped():
    """note 必填是防腐設計：說不出防的是哪種壞掉的，就不該進這個檔。"""
    raw = {"profiles": [{"match_arch": ["x"], "extra_body": {"a": "1"}}]}
    assert mp.normalize(raw)["profiles"] == []


def test_entries_without_extra_body_are_dropped():
    raw = {"profiles": [{"match_arch": ["x"], "note": "有話說但沒設定"}]}
    assert mp.normalize(raw)["profiles"] == []


def test_shipped_file_loads_and_is_valid():
    """實際出貨的那份檔案必須載得起來，而且每一條都合規。"""
    profiles = mp.load_profiles()
    assert isinstance(profiles, list)
    for entry in profiles:
        assert entry["note"].strip(), "每條 profile 都要說明它防的是什麼"
        assert entry["extra_body"]


def test_shipped_file_matches_lmstudio_mlx_arch_string():
    """R18 修的 bug：LM Studio 的 MLX 建置回報 arch='qwen3_5'（底線），GGUF
    建置回報 'qwen35'——九次審查都沒抓到，是因為既有測試全部手餵
    arch='qwen35' 這個 fixture 字串，從沒對過出貨檔案本身。這裡故意不傳
    profiles 參數，逼 profile_for 去讀真正會被使用者機器載入的
    model_profiles.yaml。"""
    hit = mp.profile_for(DetectedModel(id="m", backend="lmstudio", base_url="http://x/v1", arch="qwen3_5"))
    assert hit is not None, "qwen3_5（MLX 建置）必須命中出貨的 qwen 家族 profile"
    assert hit["extra_body"] == {"reasoning_effort": "none"}


def test_missing_file_fails_soft(tmp_path):
    assert mp.load_profiles(str(tmp_path / "nope.yaml")) == []


def test_recommended_model_falls_back_when_ram_unknown():
    assert mp.recommended_model(None) == "qwen2.5:3b"


def test_recommended_model_uses_fallback_when_tiers_empty():
    """分層表還沒填實測型號之前，RAM 不影響任何事。"""
    data = {"recommended_models": [], "fallback": "qwen2.5:3b"}
    assert mp.recommended_model(64 * 1024**3, data) == "qwen2.5:3b"


def test_recommended_model_picks_the_matching_tier():
    data = {
        "recommended_models": [
            {"max_ram_gb": 8, "model": "small"},
            {"max_ram_gb": 24, "model": "medium"},
            {"max_ram_gb": None, "model": "large"},
        ],
        "fallback": "qwen2.5:3b",
    }
    assert mp.recommended_model(8 * 1024**3, data) == "small"
    assert mp.recommended_model(16 * 1024**3, data) == "medium"
    assert mp.recommended_model(64 * 1024**3, data) == "large"
