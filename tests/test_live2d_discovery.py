import pytest

from src.open_llm_vtuber.live2d_discovery import is_discoverable_live2d_dir


@pytest.mark.parametrize("name", ["mao", "kurisu", "Hiyori_Pro_t11"])
def test_normal_live2d_directories_are_discoverable(name: str) -> None:
    assert is_discoverable_live2d_dir(name)


@pytest.mark.parametrize(
    "name",
    [".cache", ".Hiyori", "Hiyori.bak", "Hiyori.bak.20260804", "Hiyori~"],
)
def test_hidden_and_backup_live2d_directories_are_filtered(name: str) -> None:
    assert not is_discoverable_live2d_dir(name)
