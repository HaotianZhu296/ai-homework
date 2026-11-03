import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

import app as app_module  # noqa: E402
from app import app  # noqa: E402
from db import connect  # noqa: E402
from import_data import SAMPLE_CSV  # noqa: E402

SMALL_CSV = """id,text,annotations
1,Great job!,"[""positive"", ""positive"", ""sarcastic""]"
2,Not good at all.,"[""negative"", ""negative"", ""negative""]"
3,It works as expected.,"[""neutral"", ""neutral"", ""positive""]"
4,"Oh sure, best idea ever.","[""sarcastic"", ""sarcastic"", ""positive""]"
"""


@pytest.fixture()
def small_csv(tmp_path):
    path = tmp_path / "small.csv"
    path.write_text(SMALL_CSV, encoding="utf-8")
    return path


@pytest.fixture()
def conn(tmp_path):
    c = connect(tmp_path / "unit.db")
    yield c
    c.close()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """App with a fresh database, bootstrapped from the bundled sample dataset."""
    # Tests assume the sample's shape even if the official CSV is also present.
    monkeypatch.setattr(app_module, "default_csv", lambda: SAMPLE_CSV)
    app.state.db_path = tmp_path / "app.db"
    with TestClient(app) as c:
        yield c
    del app.state.db_path
