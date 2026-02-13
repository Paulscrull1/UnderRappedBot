"""Тесты обработчиков (логика, без реального Telegram)."""


def test_build_card_caption():
    from handlers.track_card_handler import build_card_caption
    track = {"title": "Song", "artist": "Band", "genre": "Rock"}
    cap = build_card_caption(track)
    assert "Song" in cap
    assert "Band" in cap
    assert "Rock" in cap


def test_download_key():
    from handlers.track_card_handler import _download_key
    k = _download_key(123, "t:a")
    assert k == (123, "t:a")
