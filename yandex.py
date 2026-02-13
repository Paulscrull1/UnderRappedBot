# Обратная совместимость: старый импорт from yandex import search_track
from yandex_music_service import search_tracks


def search_track(query, limit=1):
    return search_tracks(query, limit=limit)
