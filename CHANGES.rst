Changes
~~~~~~~

.. Future (?)
.. ----------
.. -

0.6.5 (2019-05-05)
------------------
- Simplify repo structure
- Fix package namespace issues


0.6.2 (2019-01-29)
------------------
- Add module install to copy command. This is useful for installing
  test instance overlays.
- Add rawsql execution to init + copy. This can be useful to template
  basic database seeding programatically.
- Refactor backup to snapshotting command leveraging rsync.

0.6.1 (2019-01-25)
------------------
- Include copy + backup commands
- Coerce backup command to only include public schema on pg_dump. This ensures
  restoring in a scenario where the db user is not superuser role
  and an EXTENSION was installed. Anything other than in the public scheme
  will not be exported.

0.6.0 (2019-01-24)
------------------
- Refactor to dodoo plugin

0.5.2 (2019-01-22)
------------------
- Do not limit db regex: quoted identifiers have no limiting spec.

0.5.1 (2018-12-05)
------------------
- Add addons-path option

0.5.0 (2018-11-04)
--------------------
- First dodoo release
