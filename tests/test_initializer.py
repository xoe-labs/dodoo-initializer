#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
# This file is part of the dodoo-initializer (R) project.
# Copyright (c) 2018 ACSONE SA/NV and XOE Corp. SAS
# Authors: Stéphane Bidoul, Thomas Binsfeld, Benjamin Willig,
# David Arnold, et al.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this library; if not, see <http://www.gnu.org/licenses/>.
#
import os
import subprocess
import sys
import textwrap
from datetime import datetime, timedelta

import click_odoo
import mock
import pytest
from click.testing import CliRunner

from src import initializer

TEST_DBNAME = "dodoo-initializer-testdb"
TEST_DBNAME_NEW = "dodoo-initializer-testdb-new"
TEST_PREFIX = "tstpfx9"
TEST_HASH1 = "a" * initializer.DbCache.HASH_SIZE
TEST_HASH2 = "b" * initializer.DbCache.HASH_SIZE
TEST_HASH3 = "c" * initializer.DbCache.HASH_SIZE
TODAY = datetime(2018, 5, 10)
TODAY_MINUS_2 = datetime(2018, 5, 8)
TODAY_MINUS_4 = datetime(2018, 5, 6)
ADDONS_PATH = ",".join(
    [
        os.path.join(click_odoo.odoo.__path__[0], "addons"),
        os.path.join(click_odoo.odoo.__path__[0], "..", "addons"),
        os.path.join(os.path.dirname(__file__), "data", "test_initializer"),
    ]
)


def _dropdb(dbname):
    subprocess.check_call(["dropdb", "--if-exists", dbname])


@pytest.fixture
def pgdb():
    subprocess.check_call(["createdb", TEST_DBNAME])
    try:
        yield TEST_DBNAME
    finally:
        _dropdb(TEST_DBNAME)


@pytest.fixture
def dbcache():
    with initializer.DbCache(TEST_PREFIX) as c:
        try:
            yield c
        finally:
            c.purge()


def test_dbcache_create(pgdb, dbcache):
    assert dbcache.size == 0
    assert not dbcache.create(TEST_DBNAME_NEW, TEST_HASH1)
    with mock.patch.object(initializer, "datetime") as mock_dt:
        # create a few db with known dates
        mock_dt.utcnow.return_value = TODAY_MINUS_4
        dbcache.add(pgdb, TEST_HASH1)
        assert dbcache.size == 1
        mock_dt.utcnow.return_value = TODAY
        assert dbcache.create(TEST_DBNAME_NEW, TEST_HASH1)
        try:
            assert dbcache.size == 1
            # ensure the cached template has been "touched"
            dbcache.trim_age(timedelta(days=3))
            assert dbcache.size == 1
        finally:
            _dropdb(TEST_DBNAME_NEW)
        # test recreate (same day)
        assert dbcache.create(TEST_DBNAME_NEW, TEST_HASH1)
        _dropdb(TEST_DBNAME_NEW)


def test_dbcache_purge(pgdb, dbcache):
    assert dbcache.size == 0
    dbcache.add(pgdb, TEST_HASH1)
    assert dbcache.size == 1
    dbcache.purge()
    assert dbcache.size == 0


def test_dbcache_trim_size(pgdb, dbcache):
    assert dbcache.size == 0
    dbcache.add(pgdb, TEST_HASH1)
    assert dbcache.size == 1
    dbcache.add(pgdb, TEST_HASH2)
    assert dbcache.size == 2
    dbcache.add(pgdb, TEST_HASH3)
    assert dbcache.size == 3
    dbcache.trim_size(max_size=2)
    assert dbcache.size == 2
    result = CliRunner().invoke(
        initializer.main,
        [
            "--cache-prefix",
            TEST_PREFIX,
            "--cache-max-size",
            "-1",
            "--cache-max-age",
            "-1",
        ],
    )
    assert result.exit_code == 0
    assert dbcache.size == 2
    result = CliRunner().invoke(
        initializer.main,
        [
            "--cache-prefix",
            TEST_PREFIX,
            "--cache-max-size",
            "1",
            "--cache-max-age",
            "-1",
        ],
    )
    assert result.exit_code == 0
    assert dbcache.size == 1
    result = CliRunner().invoke(
        initializer.main,
        [
            "--cache-prefix",
            TEST_PREFIX,
            "--cache-max-size",
            "0",
            "--cache-max-age",
            "-1",
        ],
    )
    assert result.exit_code == 0
    assert dbcache.size == 0


def test_dbcache_trim_age(pgdb, dbcache):
    assert dbcache.size == 0
    with mock.patch.object(initializer, "datetime") as mock_dt:
        # create a few db with known dates
        mock_dt.utcnow.return_value = TODAY
        dbcache.add(pgdb, TEST_HASH1)
        assert dbcache.size == 1
        mock_dt.utcnow.return_value = TODAY_MINUS_2
        dbcache.add(pgdb, TEST_HASH2)
        assert dbcache.size == 2
        mock_dt.utcnow.return_value = TODAY_MINUS_4
        dbcache.add(pgdb, TEST_HASH3)
        assert dbcache.size == 3
        # get back to TODAY
        mock_dt.utcnow.return_value = TODAY
        # trim older than 5 days: no change
        dbcache.trim_age(timedelta(days=5))
        assert dbcache.size == 3
        # trim older than 3 days: drop one
        dbcache.trim_age(timedelta(days=3))
        assert dbcache.size == 2
        # do nothing
        result = CliRunner().invoke(
            initializer.main,
            [
                "--cache-prefix",
                TEST_PREFIX,
                "--cache-max-size",
                "-1",
                "--cache-max-age",
                "-1",
            ],
        )
        assert result.exit_code == 0
        assert dbcache.size == 2
        # drop older than 1 day, drop one
        result = CliRunner().invoke(
            initializer.main,
            [
                "--cache-prefix",
                TEST_PREFIX,
                "--cache-max-size",
                "-1",
                "--cache-max-age",
                "1",
            ],
        )
        assert result.exit_code == 0
        assert dbcache.size == 1
        # drop today too, drop everything
        result = CliRunner().invoke(
            initializer.main,
            [
                "--cache-prefix",
                TEST_PREFIX,
                "--cache-max-size",
                "-1",
                "--cache-max-age",
                "0",
            ],
        )
        assert result.exit_code == 0
        assert dbcache.size == 0


def test_create_cmd_cache(dbcache, tmpdir, mocker):
    assert dbcache.size == 0
    try:
        result = CliRunner().invoke(
            initializer.main,
            ["--cache-prefix", TEST_PREFIX, "-n", TEST_DBNAME_NEW, "-m", "auth_signup"],
        )
        assert result.exit_code == 0
        assert dbcache.size == 1
        self = mocker.patch("click_odoo.CommandWithOdooEnv")
        self.database = TEST_DBNAME_NEW
        with click_odoo.OdooEnvironment(self) as env:
            m = env["ir.module.module"].search(
                [("name", "=", "auth_signup"), ("state", "=", "installed")]
            )
            assert m, "auth_signup module not installed"
            env.cr.execute(
                """
                SELECT COUNT(*) FROM ir_attachment
                WHERE store_fname IS NOT NULL
            """
            )
            assert env.cr.fetchone()[0] == 0, "some attachments are not stored in db"
    finally:
        _dropdb(TEST_DBNAME_NEW)
    # try again, from cache this time
    with mock.patch.object(initializer, "odoo_createdb") as m:
        try:
            result = CliRunner().invoke(
                initializer.main,
                [
                    "--cache-prefix",
                    TEST_PREFIX,
                    "--new-database",
                    TEST_DBNAME_NEW,
                    "--modules",
                    "auth_signup",
                ],
            )
            assert result.exit_code == 0
            assert m.call_count == 0
            assert dbcache.size == 1
        finally:
            _dropdb(TEST_DBNAME_NEW)
        # now run again, with a new addon in path
        # and make sure the list of modules has been updated
        # after creating the database from cache
        odoo_cfg = tmpdir / "odoo.cfg"
        odoo_cfg.write(
            textwrap.dedent(
                """\
            [options]
            addons_path = {}
        """.format(
                    ADDONS_PATH
                )
            )
        )
        cmd = [
            sys.executable,
            "-m",
            "src.initializer",
            "-c",
            str(odoo_cfg),
            "--cache-prefix",
            TEST_PREFIX,
            "--new-database",
            TEST_DBNAME_NEW,
            "--modules",
            "auth_signup",
        ]
        try:
            subprocess.check_call(cmd)
            self = mocker.patch("click_odoo.CommandWithOdooEnv")
            self.database = TEST_DBNAME_NEW
            with click_odoo.OdooEnvironment(self) as env:
                assert env["ir.module.module"].search(
                    [("name", "=", "addon1")]
                ), "module addon1 not present in new database"
        finally:
            _dropdb(TEST_DBNAME_NEW)


def test_create_cmd_nocache(dbcache, mocker):
    assert dbcache.size == 0
    try:
        result = CliRunner().invoke(
            initializer.main, ["--no-cache", "-n", TEST_DBNAME_NEW, "-m", "auth_signup"]
        )
        assert result.exit_code == 0
        assert dbcache.size == 0
        self = mocker.patch("click_odoo.CommandWithOdooEnv")
        self.database = TEST_DBNAME_NEW
        with click_odoo.OdooEnvironment(self) as env:
            m = env["ir.module.module"].search(
                [("name", "=", "auth_signup"), ("state", "=", "installed")]
            )
            assert m, "auth_signup module not installed"
            env.cr.execute(
                """
                SELECT COUNT(*) FROM ir_attachment
                WHERE store_fname IS NULL
            """
            )
            assert (
                env.cr.fetchone()[0] == 0
            ), "some attachments are not stored in filestore"
    finally:
        _dropdb(TEST_DBNAME_NEW)


def test_dbcache_add_concurrency(pgdb, dbcache):
    assert dbcache.size == 0
    dbcache.add(pgdb, TEST_HASH1)
    assert dbcache.size == 1
    dbcache.add(pgdb, TEST_HASH1)
    assert dbcache.size == 1
