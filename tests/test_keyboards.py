"""Тесты клавиатур: наличие кнопок и callback_data."""
from telegram import InlineKeyboardButton
from keyboards import (
    main_menu,
    rating_buttons,
    back_to_menu_button,
    track_card_buttons,
    chart_list_buttons,
)


def _collect_callback_data(markup):
    data = []
    for row in markup.inline_keyboard:
        for btn in row:
            if getattr(btn, "callback_data", None):
                data.append(btn.callback_data)
    return data


def test_main_menu():
    mk = main_menu()
    data = _collect_callback_data(mk)
    assert "show_daily_track" in data
    assert "show_chart" in data
    assert "start_search" in data
    assert "view_reviews" in data
    assert "view_global_reviews" in data
    assert "back_to_menu" not in data


def test_rating_buttons():
    mk = rating_buttons()
    data = _collect_callback_data(mk)
    for i in range(1, 11):
        assert f"rate_{i}" in data
    assert "cancel_rating" in data


def test_back_to_menu_button():
    mk = back_to_menu_button()
    data = _collect_callback_data(mk)
    assert data == ["back_to_menu"]


def test_track_card_buttons():
    from utils import hash_id
    mk = track_card_buttons("123:456", "https://example.com", False)
    data = _collect_callback_data(mk)
    h = hash_id("123:456")
    assert f"rate_track_{h}" in data
    assert f"ask_review_{h}" in data
    assert f"download_track_{h}" in data
    assert f"fav_toggle_{h}" in data
    assert "back_to_menu" in data


def test_chart_list_buttons():
    tracks = [{"id": "1:2", "title": "T", "artist": "A"}]
    mk = chart_list_buttons(tracks)
    data = _collect_callback_data(mk)
    assert len(data) == 2  # one track + back
    assert "back_to_menu" in data
