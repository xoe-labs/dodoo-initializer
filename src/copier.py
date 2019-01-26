#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2018 ACSONE SA/NV (<http://acsone.eu>)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

import os
import shutil

import click
import dodoo
from dodoo import odoo
from psycopg2.extensions import AsIs, quote_ident

from ._dbutils import db_exists, pg_connect, terminate_connections


def _copy_db(cr, source, dest):
    cr.execute(
        "CREATE DATABASE %s WITH TEMPLATE %s",
        (AsIs(quote_ident(dest, cr)), AsIs(quote_ident(source, cr))),
    )


def _copy_filestore(source, dest):
    filestore_source = odoo.tools.config.filestore(source)
    if os.path.isdir(filestore_source):
        filestore_dest = odoo.tools.config.filestore(dest)
        shutil.copytree(filestore_source, filestore_dest)


@click.command(cls=dodoo.CommandWithOdooEnv)
@click.option(
    "--force-disconnect",
    "-f",
    is_flag=True,
    help="Attempt to disconnect users from the template database.",
)
@click.option(
    "--modules",
    "-m",
    show_default=True,
    help="Comma separated list of addons to install.",
)
@click.argument("source", required=True)
@click.argument("dest", required=True)
def copy(env, source, dest, force_disconnect, modules):
    """ Create an Odoo database by copying an existing one.

    This script copies using postgres CREATEDB WITH TEMPLATE.
    It also copies the filestore.
    """
    with pg_connect() as cr:
        if db_exists(dest):
            msg = "Destination database already exists: {}".format(dest)
            raise click.ClickException(msg)
        if not db_exists(source):
            msg = "Source database does not exist: {}".format(source)
            raise click.ClickException(msg)
        if force_disconnect:
            terminate_connections(source)
        _copy_db(cr, source, dest)
    _copy_filestore(source, dest)

    module_names = [m.strip() for m in modules.split(",")]
    if module_names:
        odoo.tools.config["init"] = dict.fromkeys(module_names, 1)
        if odoo.release.version_info[0] < 10:
            Registry = odoo.modules.registry.RegistryManager
        else:
            Registry = odoo.modules.registry.Registry
        Registry.new(dest, force_demo=False, update_module=True)
        odoo.sql_db.close_db(dest)


if __name__ == "__main__":  # pragma: no cover
    copy()
