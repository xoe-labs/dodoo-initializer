# Copyright 2018 ACSONE SA/NV (<http://acsone.eu>)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

import os
import shutil
import subprocess
from filecmp import dircmp

import pytest
from click.testing import CliRunner
from dodoo import odoo

from src import backuper
from src._dbutils import db_exists

TEST_DBNAME = "dodoo-cruder-testbackupdb"
TEST_FILESTORE_FILE = "/dir1/f.txt"


def _dropdb(dbname):
    subprocess.check_call(["dropdb", "--if-exists", dbname])


def _dropdb_odoo(dbname):
    _dropdb(dbname)
    filestore_dir = odoo.tools.config.filestore(dbname)
    if os.path.isdir(filestore_dir):
        shutil.rmtree(filestore_dir)


def _createdb(dbname):
    subprocess.check_call(["createdb", dbname])


@pytest.fixture
def filestore():
    filestore_dir = odoo.tools.config.filestore(TEST_DBNAME)
    os.makedirs(filestore_dir)
    filstore_file = os.path.join(filestore_dir, *TEST_FILESTORE_FILE.split("/"))
    os.makedirs(os.path.dirname(filstore_file))
    with open(filstore_file, "w") as f:
        f.write("Hello world")
    try:
        yield
    finally:
        shutil.rmtree(filestore_dir)


@pytest.fixture
def pgdb():
    _createdb(TEST_DBNAME)
    try:
        yield TEST_DBNAME
    finally:
        _dropdb(TEST_DBNAME)


@pytest.fixture
def manifest():
    _original_f = odoo.service.db.dump_db_manifest
    try:
        odoo.service.db.dump_db_manifest = lambda a: {"manifest": "backupdb"}
        yield
    finally:
        odoo.service.db.dump_db_manifest = _original_f


def _check_backup(backup_dir):
    assert os.path.exists(
        os.path.join(backuper._latest_snapshot(backup_dir), "dump.sql")
    ) or os.path.exists(os.path.join(backuper._latest_snapshot(backup_dir), "db.dump"))
    assert os.path.exists(
        os.path.join(
            backuper._latest_snapshot(backup_dir),
            "filestore",
            *TEST_FILESTORE_FILE.split("/")[1:]
        )
    )
    assert os.path.exists(
        os.path.join(backuper._latest_snapshot(backup_dir), "manifest.json")
    )


def _compare_filestore(dbname1, dbname2):
    filestore_dir_1 = odoo.tools.config.filestore(dbname1)
    filestore_dir_2 = odoo.tools.config.filestore(dbname2)
    if not os.path.exists(filestore_dir_1):
        # Odoo 8 wihout filestore
        assert not os.path.exists(filestore_dir_2)
        return
    diff = dircmp(filestore_dir_1, filestore_dir_2)
    assert not diff.left_only
    assert not diff.right_only
    assert not diff.diff_files


def tests_backupdb_folder(pgdb, filestore, tmp_path, manifest):
    backup_path = tmp_path.joinpath("backup2")
    assert not backup_path.exists()
    backup_dir = backup_path.as_posix()
    result = CliRunner().invoke(backuper.snapshot, [TEST_DBNAME, backup_dir])
    assert result.exit_code == 0, result.output
    assert backup_path.exists()
    _check_backup(backup_dir)


def tests_backupdb_not_exists():
    assert not db_exists(TEST_DBNAME)
    result = CliRunner().invoke(backuper.snapshot, [TEST_DBNAME, "out"])
    assert result.exit_code != 0
    assert "Database does not exist" in result.output


def tests_backupdb_folder_restore(odoodb, odoocfg, tmp_path):
    """Test the compatibility of the db dump file of a folder backup
    with native Odoo restore API
    """
    backup_path = tmp_path.joinpath("backup")
    assert not backup_path.exists()
    backup_dir = backup_path.as_posix()
    result = CliRunner().invoke(backuper.snapshot, [odoodb, backup_dir])
    assert result.exit_code == 0, result.output
    assert backup_path.exists()
    try:
        assert not db_exists(TEST_DBNAME)
        dumpfile = os.path.join(backuper._latest_snapshot(backup_dir), "db.dump")
        with odoo.api.Environment.manage():
            odoo.service.db.restore_db(TEST_DBNAME, dumpfile, copy=True)
            odoo.sql_db.close_db(TEST_DBNAME)
        assert db_exists(TEST_DBNAME)
    finally:
        _dropdb_odoo(TEST_DBNAME)
