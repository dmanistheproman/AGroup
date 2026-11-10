"""Generated data sets shared by the generator tests and the business-rule tests. Generating is the slow part of
the test run, so each set is made once per run; tests that change data work on a copy."""
import sqlite3
from contextlib import closing

import pytest

from backend.data_generator import generate

SCALE = 0.1         # about a tenth of the full data set, so the tests stay quick
SMALL_SCALE = 0.05


def quiet(*_):
    pass


@pytest.fixture(scope="session")
def generated(tmp_path_factory):
    """(path, counts) of a data set made with seed 314."""
    path = tmp_path_factory.mktemp("data") / "test-data.sqlite3"
    return path, generate(path, seed=314, scale=SCALE, log=quiet)


@pytest.fixture(scope="session")
def regenerated(tmp_path_factory):
    """A small set made with another seed (77), then made again over it with reset=True and the same seed:
    (path, first counts, accounts and projects of the first run, second counts)."""
    path = tmp_path_factory.mktemp("reset") / "reset.sqlite3"
    first = generate(path, seed=77, scale=SMALL_SCALE, log=quiet)
    with closing(sqlite3.connect(path)) as connection:
        before = (connection.execute("SELECT email FROM user_account ORDER BY user_id").fetchall(),
                  connection.execute("SELECT title FROM projects ORDER BY id").fetchall())
    second = generate(path, seed=77, scale=SMALL_SCALE, reset=True, log=quiet)
    return path, first, before, second
