# yandex_music_service.py
# Единый слой работы с API Яндекс.Музыки (библиотека yandex-music)
import re
import random
import config

_client = None
_chart_cache = None
_chart_cache_ts = 0
CHART_CACHE_TTL = 3600  # 1 час


def _get_client():
    """Ленивая инициализация клиента."""
    global _client
    if _client is None:
        token = config.YANDEX_MUSIC_TOKEN or None
        _client = Client(token).init() if token else Client().init()
    return _client


def _track_id_from_short(track_short):
    """Из TrackShort получаем строковый id вида 'track_id:album_id'."""
    tr = getattr(track_short, "track", track_short)
    tid = getattr(tr, "track_id", None)
    if tid:
        return str(tid)
    # fallback
    mid = getattr(tr, "id", None)
    albums = getattr(tr, "albums", []) or []
    aid = albums[0].id if albums else None
    if mid is not None and aid is not None:
        return f"{mid}:{aid}"
    return str(mid) if mid is not None else None


def _cover_url_from_track(track_or_short):
    """Строит URL обложки из cover_uri (Track или TrackShort)."""
    tr = getattr(track_or_short, "track", track_or_short)
    uri = getattr(tr, "cover_uri", None)
    if not uri:
        return None
    if not uri.startswith("http"):
        uri = "https://" + uri
    return uri.replace("%%", "200x200")


def _artist_name(track_or_short):
    """Имя исполнителя (первый из списка)."""
    tr = getattr(track_or_short, "track", track_or_short)
    artists = getattr(tr, "artists", []) or []
    if not artists:
        return "Неизвестен"
    return artists[0].name if hasattr(artists[0], "name") else str(artists[0])


def _genre_from_track(track_or_short):
    """Жанр из альбома или трека."""
    tr = getattr(track_or_short, "track", track_or_short)
    genre = getattr(tr, "genre", None)
    if genre:
        return genre if isinstance(genre, str) else getattr(genre, "name", "—")
    albums = getattr(tr, "albums", []) or []
    if albums and hasattr(albums[0], "genre"):
        g = albums[0].genre
        return g if isinstance(g, str) else getattr(g, "name", "—")
    return "—"


def _to_track_dict(track_short, track_id=None):
    """Преобразует TrackShort в единый словарь для бота."""
    tr = getattr(track_short, "track", track_short)
    tid = track_id or _track_id_from_short(track_short)
    title = getattr(tr, "title", "") or "Без названия"
    artist = _artist_name(track_short)
    cover_url = _cover_url_from_track(track_short)
    genre = _genre_from_track(track_short)
    album_id = None
    if tr and getattr(tr, "albums", None):
        albums = tr.albums
        if albums:
            album_id = getattr(albums[0], "id", None)
    track_url = None
    if tid and album_id:
        # формат: https://music.yandex.ru/album/{album_id}/track/{track_id}
        parts = str(tid).split(":")
        if len(parts) >= 2:
            track_url = f"https://music.yandex.ru/album/{parts[1]}/track/{parts[0]}"
        else:
            track_url = f"https://music.yandex.ru/album/{album_id}/track/{parts[0]}"
    if not track_url and tid:
        track_url = f"https://music.yandex.ru/search?text={artist}+{title}"
    return {
        "id": tid,
        "title": title,
        "artist": artist,
        "cover_url": cover_url or "",
        "genre": genre,
        "track_url": track_url,
    }


try:
    from yandex_music import Client
except ImportError:
    Client = None


def get_chart_tracks(chart_id="world", limit=20):
    """
    Возвращает список треков из чарта.
    Без токена может не работать в части регионов.
    """
    if Client is None:
        return []
    try:
        global _chart_cache, _chart_cache_ts
        import time
        now = time.time()
        if _chart_cache is not None and (now - _chart_cache_ts) < CHART_CACHE_TTL:
            tracks = _chart_cache[:limit]
            return [_to_track_dict(t) for t in tracks]
        client = _get_client()
        chart_response = client.chart(chart_id)
        pl = getattr(chart_response, "chart", None)
        if not pl or not getattr(pl, "tracks", None):
            return []
        raw = pl.tracks[:limit]
        _chart_cache = pl.tracks
        _chart_cache_ts = now
        return [_to_track_dict(ts) for ts in raw]
    except Exception as e:
        print(f"yandex_music_service get_chart_tracks error: {e}")
        return []


def get_daily_track():
    """
    Трек дня: один и тот же для всех пользователей, обновляется раз в 24 часа.
    Сначала проверяет кэш в БД, при истечении или отсутствии — выбирает новый из чарта.
    """
    from database import get_cached_daily_track, set_daily_track

    cached = get_cached_daily_track()
    if cached:
        track_id = cached[0]
        track = get_track_by_id(track_id)
        if track:
            return track
        # Трек удалён или недоступен — выберем новый
    tracks = get_chart_tracks(chart_id="world", limit=50)
    if not tracks:
        return None
    track = random.choice(tracks)
    set_daily_track(track["id"])
    return track


def search_tracks(query, limit=5):
    """
    Поиск по запросу. Ожидается формат «Автор — Название» или любой текст.
    Возвращает список словарей с ключами id, title, artist, cover_url, genre, track_url.
    """
    if Client is None:
        return []
    try:
        client = _get_client()
        search_result = client.search(query)
        if not search_result or not getattr(search_result, "tracks", None):
            return []
        tracks_list = search_result.tracks
        if not getattr(tracks_list, "results", None):
            return []
        results = tracks_list.results[:limit]
        out = []
        for track_short in results:
            d = _to_track_dict(track_short)
            if d.get("id"):
                out.append(d)
        return out
    except Exception as e:
        print(f"yandex_music_service search_tracks error: {e}")
        return []


def get_track_object(track_id):
    """
    Возвращает объект Track из библиотеки yandex_music для скачивания и т.д.
    """
    if Client is None or not track_id:
        return None
    try:
        parts = str(track_id).split(":")
        if len(parts) < 2:
            return None
        client = _get_client()
        tracks = client.tracks([track_id])
        if not tracks or len(tracks) == 0:
            return None
        return tracks[0]
    except Exception as e:
        print(f"yandex_music_service get_track_object error: {e}")
        return None


def download_track_bytes(track_id, codec="mp3", bitrate_in_kbps=192):
    """
    Скачивает трек через API (как в документации библиотеки).
    Возвращает (bytes, title, performer) или (None, None, None) при ошибке.
    Для полного скачивания нужен токен Яндекс.Музыки.
    """
    track = get_track_object(track_id)
    if not track:
        return None, None, None
    try:
        data = track.download_bytes(codec=codec, bitrate_in_kbps=bitrate_in_kbps)
        title = getattr(track, "title", "") or "Track"
        artists = getattr(track, "artists", []) or []
        performer = ", ".join(getattr(a, "name", str(a)) for a in artists) or "Unknown"
        return data, title, performer
    except Exception as e:
        print(f"yandex_music_service download_track_bytes error: {e}")
        return None, None, None


def _parse_playlist_url(url: str):
    """
    Парсит ссылку на плейлист Яндекс.Музыки.
    Возвращает (owner_id, kind) или None.
    Поддерживает форматы:
    - https://music.yandex.ru/playlists/owner.kind (например lk.7517ecdf-7b39-4bfe-bcd9-ab8606d6b063)
    - https://music.yandex.ru/users/owner/playlists/kind
    """
    url = (url or "").strip()
    if not url:
        return None
    # users/owner/playlists/kind
    m = re.search(r"music\.yandex\.(?:ru|com)/users/([^/]+)/playlists/([^/?]+)", url, re.I)
    if m:
        return m.group(1), m.group(2)
    # /playlists/owner.kind
    m = re.search(r"music\.yandex\.(?:ru|com)/playlists/([^/?]+)", url, re.I)
    if not m:
        return None
    part = m.group(1)
    if "." in part:
        owner, kind = part.split(".", 1)
        return owner.strip(), kind.strip()
    return None


def get_playlist_tracks(playlist_url: str, limit: int = 500):
    """
    Возвращает список треков из плейлиста по ссылке.
    Формат треков как у get_chart_tracks: id, title, artist, cover_url, genre, track_url.
    При ошибке возвращает пустой список.
    """
    if Client is None:
        return []
    parsed = _parse_playlist_url(playlist_url)
    if not parsed:
        return []
    owner_id, kind = parsed
    try:
        client = _get_client()
        playlist = client.users_playlists(kind=kind, user_id=owner_id)
        if not playlist:
            return []
        if not getattr(playlist, "fetch_tracks", None):
            tracks_raw = getattr(playlist, "tracks", []) or []
        else:
            playlist.fetch_tracks()
            tracks_raw = getattr(playlist, "tracks", []) or []
        out = []
        for item in tracks_raw[:limit]:
            track_short = getattr(item, "track", item)
            if not track_short:
                continue
            d = _to_track_dict(track_short)
            if d.get("id"):
                out.append(d)
        return out
    except Exception as e:
        print(f"yandex_music_service get_playlist_tracks error: {e}")
        return []


def get_track_by_id(track_id):
    """
    По track_id (строка 'track_id:album_id') возвращает полный словарь для карточки
    или None при ошибке.
    """
    if Client is None or not track_id:
        return None
    try:
        client = _get_client()
        parts = str(track_id).split(":")
        if len(parts) < 2:
            return None
        tid, album_id = parts[0], parts[1]
        tracks = client.tracks([track_id])
        if not tracks or len(tracks) == 0:
            return None
        track = tracks[0]
        title = getattr(track, "title", "") or "Без названия"
        artists = getattr(track, "artists", []) or []
        artist = artists[0].name if artists else "Неизвестен"
        cover_url = _cover_url_from_track(track)
        genre = _genre_from_track(track)
        track_url = f"https://music.yandex.ru/album/{album_id}/track/{tid}"
        return {
            "id": track_id,
            "title": title,
            "artist": artist,
            "cover_url": cover_url or "",
            "genre": genre,
            "track_url": track_url,
        }
    except Exception as e:
        print(f"yandex_music_service get_track_by_id error: {e}")
        return None
