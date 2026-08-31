"""GET/POST /api/perf's gpt_sovits_tts fields: prompt_text / text_lang / prompt_lang.

Only two of the nine gpt_sovits_tts leaves (api_url, ref_audio_path) were ever
readable/writable from the UI. prompt_text is the reference clip's transcript —
without it GPT-SoVITS's voice cloning is poor or fails outright — and text_lang /
prompt_lang are real user-facing choices (reply language vs. reference-clip
language). This file pins down _tts_from_conf (the GET side) and _write_tts (the
POST side) for those three new leaves.

Same convention as tests/test_llm_provider_write.py / tests/test_character_fields.py:
call the route module's helper functions directly against a tmp_path conf.yaml
(monkeypatch.chdir), never a real request or the real conf.yaml.

The fixture conf.yaml deliberately mirrors the danger the module's own header
comment calls out: several *_tts sub-blocks share leaf names (cosyvoice_tts
and cosyvoice2_tts also have a `prompt_text:` leaf; x_tts has no gpt_sovits
leaves at all) — a flat, unscoped rewrite would silently clobber the wrong
engine's block or bleed past gpt_sovits_tts into the next sibling.
"""

from src.open_llm_vtuber.perf_route import _tts_from_conf, _write_tts


def _write_conf(tmp_path, gpt_sovits_block: str) -> None:
    (tmp_path / "conf.yaml").write_text(
        "character_config:\n"
        "  tts_config:\n"
        "    tts_model: 'edge_tts'\n"
        "\n"
        "    x_tts:\n"
        "      api_url: 'http://127.0.0.1:8020/tts_to_audio'\n"
        "      speaker_wav: 'female'\n"
        "      language: 'en'\n"
        "\n"
        "    cosyvoice_tts:\n"
        "      client_url: 'http://127.0.0.1:50000/'\n"
        "      prompt_text: 'COSYVOICE_SHOULD_NOT_CHANGE'\n"
        "      seed: 0\n"
        "\n"
        f"{gpt_sovits_block}"
        "\n"
        "    fish_api_tts:\n"
        "      api_key: ''\n"
        "      reference_id: ''\n"
        "      latency: 'balanced'\n",
        encoding="utf-8",
    )


GPT_SOVITS_BLOCK = (
    "    gpt_sovits_tts:\n"
    "      # put ref audio to root path of GPT-Sovits, or set the path here\n"
    "      api_url: 'http://127.0.0.1:9880/tts'\n"
    "      text_lang: 'zh' # 文本語言\n"
    "      ref_audio_path: '' # str.(必需) 参考音频的路径\n"
    "      prompt_lang: 'zh' # str.(必需) 参考音频提示文本的语言\n"
    "      prompt_text: '' # str.(可选) 参考音频的提示文本\n"
    "      text_split_method: 'cut5'\n"
    "      batch_size: '1'\n"
    "      media_type: 'wav'\n"
    "      streaming_mode: 'false'\n"
)


def test_tts_from_conf_reads_prompt_text_and_langs(tmp_path, monkeypatch):
    block = (
        "    gpt_sovits_tts:\n"
        "      api_url: 'http://127.0.0.1:9880/tts'\n"
        "      text_lang: 'ja'\n"
        "      ref_audio_path: 'ref.wav'\n"
        "      prompt_lang: 'en'\n"
        "      prompt_text: 'this is the reference clip transcript'\n"
        "      text_split_method: 'cut5'\n"
        "      batch_size: '1'\n"
        "      media_type: 'wav'\n"
        "      streaming_mode: 'false'\n"
    )
    _write_conf(tmp_path, block)
    monkeypatch.chdir(tmp_path)

    out = _tts_from_conf()

    assert out["gpt_sovits_prompt_text"] == "this is the reference clip transcript"
    assert out["gpt_sovits_text_lang"] == "ja"
    assert out["gpt_sovits_prompt_lang"] == "en"
    # Existing fields must still round-trip correctly alongside the new ones.
    assert out["gpt_sovits_api_url"] == "http://127.0.0.1:9880/tts"
    assert out["gpt_sovits_ref_audio_path"] == "ref.wav"


def test_tts_from_conf_defaults_when_leaves_absent(tmp_path, monkeypatch):
    """An older conf.yaml predating this feature has no prompt_text/text_lang/
    prompt_lang leaves at all — the GET side must fall back to sane defaults
    instead of KeyError-ing or silently omitting the fields from the response."""
    block = (
        "    gpt_sovits_tts:\n"
        "      api_url: 'http://127.0.0.1:9880/tts'\n"
        "      ref_audio_path: ''\n"
        "      text_split_method: 'cut5'\n"
        "      batch_size: '1'\n"
        "      media_type: 'wav'\n"
        "      streaming_mode: 'false'\n"
    )
    _write_conf(tmp_path, block)
    monkeypatch.chdir(tmp_path)

    out = _tts_from_conf()

    assert out["gpt_sovits_prompt_text"] == ""
    assert out["gpt_sovits_text_lang"] == "zh"
    assert out["gpt_sovits_prompt_lang"] == "zh"


def test_write_tts_prompt_text_only_leaves_everything_else_byte_identical(
    tmp_path, monkeypatch
):
    _write_conf(tmp_path, GPT_SOVITS_BLOCK)
    conf = tmp_path / "conf.yaml"
    before = conf.read_text(encoding="utf-8").splitlines(keepends=True)
    monkeypatch.chdir(tmp_path)

    _write_tts(None, None, None, gpt_sovits_prompt_text="hello world")

    after = conf.read_text(encoding="utf-8").splitlines(keepends=True)
    assert len(before) == len(after), "write must not insert/delete lines"

    changed = [i for i in range(len(before)) if before[i] != after[i]]
    assert changed == [_line_index(before, "prompt_text:")], (
        "only the gpt_sovits_tts prompt_text line may change"
    )
    assert "prompt_text: 'hello world'" in after[changed[0]]
    # The trailing YAML comment on that exact leaf must survive the rewrite.
    assert "str.(可选)" in after[changed[0]]

    # The same-named leaf in the sibling cosyvoice_tts block must be untouched.
    assert "COSYVOICE_SHOULD_NOT_CHANGE" in "".join(after)


def test_write_tts_text_lang_only_leaves_everything_else_byte_identical(
    tmp_path, monkeypatch
):
    _write_conf(tmp_path, GPT_SOVITS_BLOCK)
    conf = tmp_path / "conf.yaml"
    before = conf.read_text(encoding="utf-8").splitlines(keepends=True)
    monkeypatch.chdir(tmp_path)

    _write_tts(None, None, None, gpt_sovits_text_lang="ja")

    after = conf.read_text(encoding="utf-8").splitlines(keepends=True)
    assert len(before) == len(after)
    changed = [i for i in range(len(before)) if before[i] != after[i]]
    assert changed == [_line_index(before, "text_lang:")]
    assert "text_lang: 'ja'" in after[changed[0]]


def test_write_tts_prompt_lang_only_leaves_everything_else_byte_identical(
    tmp_path, monkeypatch
):
    _write_conf(tmp_path, GPT_SOVITS_BLOCK)
    conf = tmp_path / "conf.yaml"
    before = conf.read_text(encoding="utf-8").splitlines(keepends=True)
    monkeypatch.chdir(tmp_path)

    _write_tts(None, None, None, gpt_sovits_prompt_lang="en")

    after = conf.read_text(encoding="utf-8").splitlines(keepends=True)
    assert len(before) == len(after)
    changed = [i for i in range(len(before)) if before[i] != after[i]]
    assert changed == [_line_index(before, "prompt_lang:")]
    assert "prompt_lang: 'en'" in after[changed[0]]
    assert "str.(必需)" in after[changed[0]], (
        "the leaf's own trailing comment must survive"
    )


def test_write_tts_all_three_together_and_read_back(tmp_path, monkeypatch):
    _write_conf(tmp_path, GPT_SOVITS_BLOCK)
    monkeypatch.chdir(tmp_path)

    _write_tts(
        None,
        None,
        None,
        gpt_sovits_prompt_text="konnichiwa",
        gpt_sovits_text_lang="ko",
        gpt_sovits_prompt_lang="ja",
    )

    out = _tts_from_conf()
    assert out["gpt_sovits_prompt_text"] == "konnichiwa"
    assert out["gpt_sovits_text_lang"] == "ko"
    assert out["gpt_sovits_prompt_lang"] == "ja"
    # api_url/ref_audio_path weren't touched by this call — still their originals.
    assert out["gpt_sovits_api_url"] == "http://127.0.0.1:9880/tts"


def _line_index(lines: list, needle: str) -> int:
    """Find `needle` strictly WITHIN the gpt_sovits_tts block (start, next
    top-level `    <name>:` sub-block). Several sibling *_tts blocks share leaf
    names (cosyvoice_tts also has `prompt_text:`), so a plain "contains" scan
    over the whole file would ambiguously match more than one block."""
    gs_start = next(i for i, ln in enumerate(lines) if ln.strip() == "gpt_sovits_tts:")
    gs_end = next(
        i
        for i in range(gs_start + 1, len(lines))
        if lines[i].strip() and not lines[i].startswith(" " * 6)
    )
    matches = [i for i in range(gs_start, gs_end) if needle in lines[i]]
    assert len(matches) == 1, (
        f"expected exactly one line containing {needle!r} inside gpt_sovits_tts"
    )
    return matches[0]
