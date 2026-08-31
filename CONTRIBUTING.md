# Contributing

How to work on `pined-django`, and how a release gets out. The
[README](README.md) is the package's own documentation — what it does and how to
use it — and is what PyPI renders, so none of this belongs there.

## Setup

```bash
uv sync --all-extras
uv run poe fix          # ruff format + ruff check --fix
uv run poe fix --check  # no writes
uv run poe test         # pytest
uv run poe cov          # pytest, with a coverage report
```

`examples/` is a settings module that runs:

```bash
DJANGO_SETTINGS_MODULE=examples.settings python -m django check
```

`tests/testapp/` is a django app whose migration chain walks a
`PydanticField` through five versions of its pydantic model, one
`AlterPydantic` feature per migration. Each schema the chain references is
committed beside it as `_schema_<model>__<field>.json`, and the shapes
those hashes stand for are kept as classes in `tests/testapp/schema_history.py`
— a pydantic release that changes `model_json_schema()` fails there, with
the fix being to regenerate both.

`tests/no_pydantic/` is the install with neither extra: the commands falling
through to django's own, and every module behind an extra naming the extra it
wants. It skips itself wherever `pydantic` is importable, and `pydantic` only
ever arrives with an extra, so:

```bash
uv sync                 # neither extra
uv run poe test-bare
uv sync --all-extras    # back to the usual one
```

## Releasing

Push a tag, and `pined-django` goes to PyPI:

```bash
git tag v0.2.0 && git push origin v0.2.0
```

The tag is the version. `.github/workflows/release.yml` writes it into
`pyproject.toml` before building, so the version committed there only matters to
a local `uv build`, and a prerelease needs nothing special: `v0.2.0rc1`. A tag
that is not a PEP 440 version — `v1.2-final` — fails at that step rather than
halfway through an upload.

The tag has to start with `v`: GitHub's tag filters document `*`, `**`, `+`, `?`
and `!`, and nothing about character ranges, so a pattern matching a bare
`1.2.3` would likely be taken literally and quietly match nothing at all.

Nothing is uploaded until `lint` and every cell of the test matrix has passed on
that exact tag — `release.yml` calls `ci.yml` and waits for it. Which also means
a tag pushed at a commit that fails CI publishes nothing, and says why.

## PyPI trusted publishing

The upload authenticates as the workflow itself, so there is no token in the
repository and nothing to rotate. It needs a publisher configured on PyPI:

- **Owner** `pinecrew`, **repository** `pined-django`, **workflow**
  `release.yml`, **environment** left empty.
- Until the first release exists, add it as a *pending publisher* — PyPI accepts
  one for a project that has never been uploaded, and that is what authorizes
  the first upload.

If you set an environment name on PyPI, `release.yml`'s `publish` job needs the
matching `environment:` key. Empty on one side and set on the other fails the
upload.

`id-token: write` on that job is what makes the identity available; it is also
what signs the attestations uploaded beside the files.

## Coverage

`poe cov` writes `coverage.xml`, and one matrix cell — the newest python and
django — reports it to [coveralls](https://coveralls.io/github/pinecrew/pined-django).
That step does not fail the cell it runs in: whether a coverage service was
reachable is not the suite's verdict. Enabling the repository on coveralls is
the whole setup; until then the step warns and passes.
