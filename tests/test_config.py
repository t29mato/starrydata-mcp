from pathlib import Path

from starrydata_mcp import config


def test_cache_dir_defaults_under_home(monkeypatch) -> None:
    monkeypatch.delenv("STARRYDATA_MCP_CACHE_DIR", raising=False)
    assert config.cache_dir() == Path.home() / ".cache" / "starrydata-mcp"


def test_cache_dir_respects_env_override(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("STARRYDATA_MCP_CACHE_DIR", str(tmp_path))
    assert config.cache_dir() == tmp_path


def test_db_path_is_inside_cache_dir(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("STARRYDATA_MCP_CACHE_DIR", str(tmp_path))
    assert config.db_path() == tmp_path / "starrydata.duckdb"


def test_rate_limit_max_requests_default(monkeypatch) -> None:
    monkeypatch.delenv("STARRYDATA_MCP_RATE_LIMIT_MAX", raising=False)
    assert config.rate_limit_max_requests() == 60


def test_rate_limit_max_requests_env_override(monkeypatch) -> None:
    monkeypatch.setenv("STARRYDATA_MCP_RATE_LIMIT_MAX", "5")
    assert config.rate_limit_max_requests() == 5


def test_rate_limit_window_seconds_default(monkeypatch) -> None:
    monkeypatch.delenv("STARRYDATA_MCP_RATE_LIMIT_WINDOW_SECONDS", raising=False)
    assert config.rate_limit_window_seconds() == 60.0


def test_rate_limit_window_seconds_env_override(monkeypatch) -> None:
    monkeypatch.setenv("STARRYDATA_MCP_RATE_LIMIT_WINDOW_SECONDS", "30.5")
    assert config.rate_limit_window_seconds() == 30.5
