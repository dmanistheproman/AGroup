"""Every test that builds the app without a database of its own gets a fresh temporary one,
so tests never change instance/agroup.sqlite3 (the database the local site uses)."""
import pytest


@pytest.fixture(autouse=True)
def separate_database(tmp_path, monkeypatch):
    monkeypatch.setenv("AGROUP_DATABASE", str(tmp_path / "agroup-test.sqlite3"))
