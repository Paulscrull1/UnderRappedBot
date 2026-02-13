"""Pytest fixtures: тестовая БД в временном файле."""
import os
import tempfile
import pytest


@pytest.fixture(scope="function")
def temp_db():
    """Временный файл БД для изоляции тестов."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    import database
    prev_path = database.DATABASE_PATH
    database.DATABASE_PATH = path
    try:
        database.init_db()
        yield path
    finally:
        database.DATABASE_PATH = prev_path
        try:
            os.unlink(path)
        except OSError:
            pass
