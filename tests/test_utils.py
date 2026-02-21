"""Тесты utils: hash_id, константы."""
import pytest
from utils import hash_id, level_progress_bar, CRITERIA_NAMES, CRITERIA, MAX_SCORE, EXP_FOR_RATING


def test_hash_id():
    h = hash_id("123:456")
    assert len(h) == 10
    assert h.isalnum()
    assert hash_id("123:456") == hash_id("123:456")
    assert hash_id("123:456") != hash_id("123:457")


def test_level_progress_bar():
    assert "1 уровня" in level_progress_bar(1, 0) or "2 уровня" in level_progress_bar(1, 0)
    bar = level_progress_bar(1, 50)
    assert "█" in bar and "░" in bar
    assert "50" in level_progress_bar(1, 50) or "до" in level_progress_bar(1, 50)


def test_criteria():
    assert len(CRITERIA) == 5
    assert "rhymes" in CRITERIA
    assert "vibe" in CRITERIA
    assert "rhymes" in CRITERIA_NAMES
    assert MAX_SCORE == 50
    assert EXP_FOR_RATING == 10
