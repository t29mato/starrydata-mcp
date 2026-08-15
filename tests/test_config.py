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
