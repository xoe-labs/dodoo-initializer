#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2018 ACSONE SA/NV (<http://acsone.eu>)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

import json
import os
import shutil
import tempfile

import click
import dodoo
from dodoo import odoo
from snapshotter import snapshotter

from ._backup import backup as do_backup
from ._dbutils import db_exists


def _latest_snapshot(path):
    return os.path.join(path, "latest.snapshot")


def _dump_db(dbname, _backup):
    cmd = ["pg_dump", "--schema=public", "--no-owner", dbname]
    filename = "dump.sql"
    if _backup.format == "folder":
        cmd.insert(-1, "--format=c")
        filename = "db.dump"
    _stdin, stdout = odoo.tools.exec_pg_command_pipe(*cmd)
    _backup.write(stdout, filename)


def _create_manifest(cr, dbname, _backup):
    manifest = odoo.service.db.dump_db_manifest(cr)
    with tempfile.NamedTemporaryFile(mode="w") as f:
        json.dump(manifest, f, indent=4)
        f.seek(0)
        _backup.addfile(f.name, "manifest.json")


def _backup_filestore(dbname, _backup):
    filestore_source = odoo.tools.config.filestore(dbname)
    if os.path.isdir(filestore_source):
        _backup.addtree(filestore_source, "filestore")


@click.command(cls=dodoo.CommandWithOdooEnv)
@click.option(
    "--min-snapshots",
    type=int,
    default=7,
    show_default=True,
    help="Minimum number of snapshots",
)
@click.option(
    "--max-snapshots",
    type=int,
    default=10,
    show_default=True,
    help="Maximum number of snapshots",
)
@click.option(
    "--unless-absent",
    default=False,
    show_default=True,
    help="Create destination directory unless it's abent",
)
@click.argument("dbname", nargs=1)
@click.argument("dest", nargs=1, required=1)
def snapshot(env, min_snapshots, max_snapshots, unless_absent, dbname, dest):
    """ Create an Odoo database snapshot from an existing one.

    This script dumps the database using pg_dump.
    It also copies the filestore.

    Unlike Odoo, this script allows you to make a backup of a
    database without going through the web interface. This
    avoids timeout and file size limitation problems when
    databases are too large.

    It also creates and maintains the specified amount of
    snapshots in the target directory. The snapshot
    implementaiton uses rsync. It hardlinks files that did not
    change. This can save a lot of disk space and bandwith
    especially for filestore items.

    (TBD) You can define a ssh destination.

    """
    if not shutil.which("rsync"):
        msg = "rsync binary not found in path."
        raise click.ClickException(msg)
    if not db_exists(dbname):
        msg = "Database does not exist: {}".format(dbname)
        raise click.ClickException(msg)
    if not os.path.exists(dest) and unless_absent:
        msg = "Destination does not exist: {}".format(dest)
        raise click.ClickException(msg)
    elif not os.path.exists(dest):
        os.makedirs(dest)
    if max_snapshots <= min_snapshots:
        msg = "--max-snapshots must be greater than --min-snapshots"
        raise click.ClickException(msg)
    db = odoo.sql_db.db_connect(dbname)
    try:
        with odoo.tools.osutil.tempdir() as temp_dir:
            with do_backup("folder", temp_dir, "w") as _backup, db.cursor() as cr:
                _create_manifest(cr, dbname, _backup)
                _backup_filestore(dbname, _backup)
                _dump_db(dbname, _backup)
            snapshotter.snapshot(temp_dir, dest, False, min_snapshots, max_snapshots)
    finally:
        odoo.sql_db.close_db(dbname)


if __name__ == "__main__":  # pragma: no cover
    snapshot()
