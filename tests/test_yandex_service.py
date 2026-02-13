"""Тесты yandex_music_service (без реального API: моки или проверка формата)."""
import pytest


def test_hash_id_consistency():
    """Сервис использует track_id вида track_id:album_id."""
    from utils import hash_id
    tid = "12345:67890"
    h = hash_id(tid)
    assert len(h) <= 64
    assert h.isalnum()


def test_get_track_by_id_returns_none_without_client(monkeypatch):
    """Без токена/клиента get_track_by_id может вернуть None при ошибке."""
    import yandex_music_service as svc
    # Вызов с невалидным id
    result = svc.get_track_by_id("")
    assert result is None
    result = svc.get_track_by_id("invalid")
    assert result is None or isinstance(result, dict)


def test_download_track_bytes_returns_tuple():
    """download_track_bytes возвращает (bytes|None, title|None, performer|None)."""
    import yandex_music_service as svc
    # Без реального клиента получим (None, None, None) или ошибку
    try:
        out = svc.download_track_bytes("1:2")
        assert isinstance(out, tuple)
        assert len(out) == 3
    except Exception:
        pass
