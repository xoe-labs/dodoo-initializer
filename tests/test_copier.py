# Copyright 2018 ACSONE SA/NV (<http://acsone.eu>)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

import os
import shutil
import subprocess

import dodoo
import pytest
from click.testing import CliRunner
from dodoo import odoo

from dodoo_dbhandler._dbutils import db_exists
from dodoo_dbhandler.copier import copy

TEST_DBNAME = "dodoo-cruder-testcopydb"
TEST_DBNAME_NEW = "dodoo-cruder-testcopydb-new"


def _dropdb(dbname):
    subprocess.check_call(["dropdb", "--if-exists", dbname])


def _createdb(dbname):
    subprocess.check_call(["createdb", dbname])


@pytest.fixture
def filestore():
    filestore_dir = odoo.tools.config.filestore(TEST_DBNAME)
    os.makedirs(filestore_dir)
    try:
        yield
    finally:
        shutil.rmtree(filestore_dir)


@pytest.fixture
def pgdb():
    subprocess.check_call(["createdb", TEST_DBNAME])
    try:
        yield TEST_DBNAME
    finally:
        _dropdb(TEST_DBNAME)


def tests_copydb(pgdb, filestore):
    filestore_dir_new = odoo.tools.config.filestore(TEST_DBNAME_NEW)
    try:
        assert not db_exists(TEST_DBNAME_NEW)
        assert not os.path.exists(filestore_dir_new)
        result = CliRunner().invoke(
            copy, ["--force-disconnect", TEST_DBNAME, TEST_DBNAME_NEW]
        )
        assert result.exit_code == 0, result.output
        # this dropdb will indirectly test that the new db exists
        subprocess.check_call(["dropdb", TEST_DBNAME_NEW])
        assert os.path.isdir(filestore_dir_new)
    finally:
        _dropdb(TEST_DBNAME_NEW)
        if os.path.isdir(filestore_dir_new):
            shutil.rmtree(filestore_dir_new)


def tests_module_install_and_raw_sql(pgdb, filestore, mocker):
    filestore_dir_new = odoo.tools.config.filestore(TEST_DBNAME_NEW)
    try:
        assert not db_exists(TEST_DBNAME_NEW)
        assert not os.path.exists(filestore_dir_new)
        result = CliRunner().invoke(
            copy,
            [
                "--force-disconnect",
                "--modules",
                "auth_signup",
                TEST_DBNAME,
                TEST_DBNAME_NEW,
                """UPDATE res_company SET name='hello' WHERE id=1""",
            ],
        )
        assert result.exit_code == 0, result.output
        self = mocker.patch("dodoo.CommandWithOdooEnv")
        self.database = TEST_DBNAME_NEW
        with dodoo.OdooEnvironment(self) as env:
            m = env["ir.module.module"].search(
                [("name", "=", "auth_signup"), ("state", "=", "installed")]
            )
            assert m, "auth_signup module not installed"
            c = env["res.company"].browse([1])
            assert c.name == "hello", "company was not renamed from rawsql"
        assert os.path.isdir(filestore_dir_new)
    finally:
        _dropdb(TEST_DBNAME_NEW)
        if os.path.isdir(filestore_dir_new):
            shutil.rmtree(filestore_dir_new)


def tests_copydb_template_absent():
    assert not db_exists(TEST_DBNAME)
    assert not db_exists(TEST_DBNAME_NEW)
    result = CliRunner().invoke(copy, [TEST_DBNAME, TEST_DBNAME_NEW])
    assert result.exit_code != 0
    assert "Source database does not exist" in result.output


def test_copydb_target_exists(pgdb):
    _createdb(TEST_DBNAME_NEW)
    try:
        assert db_exists(TEST_DBNAME)
        assert db_exists(TEST_DBNAME_NEW)
        result = CliRunner().invoke(copy, [TEST_DBNAME, TEST_DBNAME_NEW])
        assert result.exit_code != 0
        assert "Destination database already exists" in result.output
    finally:
        _dropdb(TEST_DBNAME_NEW)


def test_copydb_no_source_filestore(pgdb):
    filestore_dir_new = odoo.tools.config.filestore(TEST_DBNAME_NEW)
    try:
        result = CliRunner().invoke(
            copy, ["--force-disconnect", TEST_DBNAME, TEST_DBNAME_NEW]
        )
        assert result.exit_code == 0, result.output
        # this dropdb will indirectly test that the new db exists
        subprocess.check_call(["dropdb", TEST_DBNAME_NEW])
        assert not os.path.isdir(filestore_dir_new)
    finally:
        _dropdb(TEST_DBNAME_NEW)
