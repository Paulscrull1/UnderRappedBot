"""Тесты utils: hash_id, константы."""
import pytest
from utils import hash_id, CRITERIA_NAMES, CRITERIA, MAX_SCORE, EXP_FOR_RATING


def test_hash_id():
    h = hash_id("123:456")
    assert len(h) == 10
    assert h.isalnum()
    assert hash_id("123:456") == hash_id("123:456")
    assert hash_id("123:456") != hash_id("123:457")


def test_criteria():
    assert len(CRITERIA) == 5
    assert "rhymes" in CRITERIA
    assert "vibe" in CRITERIA
    assert "rhymes" in CRITERIA_NAMES
    assert MAX_SCORE == 50
    assert EXP_FOR_RATING == 10
