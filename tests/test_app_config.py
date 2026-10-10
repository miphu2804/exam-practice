from __future__ import annotations

from exam_practice.app_config import AppConfig


def test_defaults_are_local_with_info_logging(monkeypatch):
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
    monkeypatch.delenv("LOG__LEVEL", raising=False)

    configuration = AppConfig()

    assert configuration.hosted is False
    assert configuration.log.level == "INFO"


def test_blob_token_enables_hosted_mode(monkeypatch):
    monkeypatch.setenv("BLOB_READ_WRITE_TOKEN", "vercel_blob_rw_test")

    configuration = AppConfig()

    assert configuration.hosted is True


def test_nested_log_level_is_read_from_env(monkeypatch):
    monkeypatch.setenv("LOG__LEVEL", "DEBUG")

    configuration = AppConfig()

    assert configuration.log.level == "DEBUG"
