# Contributing

How to work on `pined-django`, and how a release gets out. The
[README](README.md) is the package's own documentation — what it does and how to
use it — and is what PyPI renders, so none of this belongs there.

## Setup

```bash
uv sync --all-extras
uv run poe lint         # ruff format --check, ruff check, pyrefly — what CI runs
uv run poe fix          # ruff format + ruff check --fix
uv run poe test         # pytest
uv run poe cov          # pytest, with a coverage report
```

`lint` reports and writes nothing; `fix` writes and reports nothing. They were
one task with a `--check` flag, which meant the checking half ran `--fix-only`
and so exited 0 whatever it found.

Pyrefly runs on the `strict` preset over `src` and `examples`, not over the
tests: those poke at private django APIs and pass deliberately wrong arguments,
and every one of those needs a suppression that repeats what the test's own name
already says. Three of strict's error kinds are off, each with its reason in
`[tool.pyrefly.errors]` — a settings part narrowing a field it inherited is how
the library is used, `*args`/`**kwargs` are the same call ruff declines to
annotate through `ANN002`/`ANN003`, and `implicit-any-lambda` fires on every
lambda there is rather than on any particular one.

What is left carries a `# pyrefly: ignore[rule]` and a reason: a private django
API the autodetector hooks into, a stub missing a method every user model has.
There are five; a sixth wants the same treatment, or a fix.

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

The tag is the version, and nothing in the repository repeats it: `version` is
`dynamic`, and `hatch-vcs` reads it out of git at build time. A prerelease needs
nothing special — `v0.2.0rc1` — and PEP 440 normalization applies, so
`v1.2.3-rc1` builds files named `1.2.3rc1`.

A build that cannot see the tag produces a development version
(`0.1.dev38+g9c4a7ad`) instead of failing, which is what a local `uv build`
gets and is exactly right there. In the release workflow it would be a silent
mispublish, so the job checks out with `fetch-depth: 0` — a shallow clone
carries no tags — and refuses to upload anything whose version carries `dev` or
a `+local` part.

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
