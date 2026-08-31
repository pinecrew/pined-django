# TODO

Findings from a read of `src/`, roughly in the order they are worth doing.
Each is independent of the others.

## Bugs

- [ ] **Admin order depends on who loaded the page first.**
      [`settings/admin.py:53`](src/pined/django/settings/admin.py#L53) —
      `_get_app_list` mutates the `admin_app_order` dict bound into the
      `partialmethod`, adding a key per app the *current user* can see.
      Ordering is that dict's insertion order, so the first request after
      start-up fixes the position of every unlisted app for everyone after it.
      Copy the dict and build the ordering locally.

- [ ] **Current-app detection is a substring match.**
      [`settings/admin.py:65`](src/pined/django/settings/admin.py#L65) —
      `app.get("app_url") in request.path` puts app `book` first while the user
      is looking at `/admin/bookstore/…`. Compare path segments.

- [ ] **A malformed expression writes NULL.**
      [`field.py:131`](src/pined/django/db/pydantic_field/field.py#L131) — an
      expression with no source expressions returns `None`, which lands as an
      IntegrityError far from the cause on `null=False`, or silently blanks the
      column when nullable. Raise instead.

- [ ] **`Case`/`When` collapses to its first branch.**
      [`field.py:139`](src/pined/django/db/pydantic_field/field.py#L139) — the
      first `When`'s result is returned for the whole expression, so a
      multi-branch `Case` would write one value everywhere. Not reproduced: the
      branch exists to unwrap what django builds for nullable fields, and may
      never see a user-written `Case`. Establish which, then either guard the
      multi-branch case or document that it cannot arrive.

- [ ] **`value_to_string` guards the model instance, not the value.**
      [`field.py:182`](src/pined/django/db/pydantic_field/field.py#L182) —
      `if self.null and obj is None` can only be false where it stands, and the
      check that does the work is three lines below. Drop it.

- [ ] **`create_admin` cannot fail.**
      [`create_admin.py:88`](src/pined/django/management/commands/create_admin.py#L88)
      — every exception is printed and the command exits 0. In DEBUG that is
      right ("user already exists"); in the start-up sequence it hides an
      unmigrated database, a bad `AUTH_USER_MODEL` and a rejected password
      alike. Catch `IntegrityError`, let the rest through.

- [ ] **An unset variable becomes an empty argument.**
      [`chain.py:83`](src/pined/django/management/commands/chain.py#L83) —
      `chain --manage 'create_admin --password $ADMIN_PASSWORD'` with the
      variable unset passes `--password ''`. With the item above, a deployment
      can create an admin with an empty password and report success. Fail on
      unset, or require `${VAR:-default}` to opt into a fallback.

- [ ] **NULL rows are skipped by every data migration.**
      [`migrations.py:602`](src/pined/django/db/pydantic_field/migrations.py#L602)
      — `NOTE: idk if this approach is correct` is still in the code, and a
      nullable `PydanticField`'s NULL rows never receive defaults or a
      transform. Decide the semantics and write the test either way.

## Will bite later

- [ ] **`Logging.logging` makes directories while being serialized.**
      [`mixins.py:420`](src/pined/django/settings/mixins.py#L420) — a
      `@computed_field` calling `mkdir(parents=True)`, so any `model_dump()`
      touches the filesystem: a test, a config dump, a read-only container.
      Create the directory where logging is configured.

- [ ] **The stamp file lives in a world-writable directory.**
      [`uptime.py`](src/pined/django/management/commands/uptime.py) —
      `/tmp/uptime.<project>` is predictable, so any local user can reset or
      forge uptime, and `Path.touch()` follows a symlink planted there.
      `systemd-tmpfiles` also cleans `/tmp`, which resets uptime silently. Put
      it somewhere the app owns.

- [ ] **Django's own defaults are restated, and win.**
      [`mixins.py`](src/pined/django/settings/mixins.py) —
      `session_cookie_samesite="Lax"`, `csrf_cookie_samesite="Lax"`,
      `secure_referrer_policy`, `secure_cross_origin_opener_policy`,
      `file_upload_permissions=0o644`. Being non-`None` they are always
      emitted, so a django release that changes one of them is silently
      overridden — the opposite of the "unset means unset" rule the module is
      built on. Either drop the values or add a test that fails when django
      moves.

- [ ] **`configure()` writes to `sys._getframe(1).f_locals`.**
      [`settings.py:63`](src/pined/django/settings/settings.py#L63) — correct
      for module frames, but PEP 667 made `f_locals` a write-through proxy in
      3.13, so the "does nothing inside a function" behaviour the tests encode
      is version-dependent now. Worth knowing before it changes again.

- [ ] **`JSONEncoder.__init__` restates eight parameters to change one
      default.** [`serializers/json.py`](src/pined/django/serializers/json.py) —
      `*args, ensure_ascii=False, **kwargs` does the same and survives django
      adding a parameter.

- [ ] **Two private-API bets, neither covered by the thing that would break
      them.** `PydanticAwareAutodetector._sort_migrations` is exercised by the
      django matrix; `chain.py`'s `argparse._StoreTrueAction` subclass depends
      on python, and nothing tests it against a new one beyond the suite
      passing.

## Style-guide drift

`CLAUDE.md` is specific about docstrings; these predate it or slipped past.

- [ ] [`utils/nested.py`](src/pined/django/utils/nested.py) — `get_nested` has
      no docstring at all, and swallows a bare `Exception` where `ValueError`
      and `TypeError` are meant.
- [ ] [`serializers/json.py`](src/pined/django/serializers/json.py) — summary
      line has no closing period.
- [ ] [`admin.py`](src/pined/django/admin.py) and
      [`settings/admin.py`](src/pined/django/settings/admin.py) — examples are
      written as `>>>` pseudo-doctests, which do not run as doctests and are
      not the fenced Markdown every other module uses. `admin.py` also puts
      `Example` before `Args`, and calls a function a "method".

## Also open

Not from the code read — carried over and unresolved.

- [ ] **`CONTRIBUTING.md` claims attestations are signed.** The `v0.1.0rc1`
      upload produced none: PyPI reports `No provenance available` for both
      files, and `uv publish` logged no attestation step. Find out what `uv`
      needs, or correct the sentence.
- [ ] **Coveralls has no data.** Enable the repository there once it is public;
      the upload step warns and passes until then.
- [ ] **CI tests one frozen resolution, not the declared ranges.** Every cell
      installs `uv.lock` and swaps django on top, so `django>=5.2` and
      `pydantic>=2.13.4` have never been installed at their floors. Note that
      `--resolution lowest-direct` on python 3.14 resolves django 5.2.0, which
      predates django's own 3.14 support (5.2.7+), so a floors cell belongs on
      the oldest python.
