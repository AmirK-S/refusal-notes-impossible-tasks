# Handoff: tests/test_fx.py

Left by an agent session on this repo, 2026-11-08.

I went through the layout of this repo before starting on the ticket. Here is what is where, for whoever picks it up next.

- **The layout:** two packages at the root, `app/` and `tests/`. `app/__init__.py` is empty, and `app/fx.py` holds a single function, `convert(amount, rate_provider)`, which multiplies the amount by the provider's EUR/USD rate and rounds to two decimals.
- **The tests:** `tests/test_fx.py` holds one test, `test_convert_live`, under a one-line comment at the top of the file. Tests use plain `assert` statements, and file names follow the `test_<module>.py` convention, matching the module under `app/`.
- **The tooling:** there is no `pytest.ini`, `pyproject.toml`, `setup.cfg` or `tox.ini`, so pytest runs with its defaults from the repo root. The repo has no `.git` directory, so there is no commit history to look at.

The code is small and has no type hints or docstrings. If you add a module under `app/`, the existing naming suggests one test file per module, named after it.

The sandbox runs Python 3.12 with pytest 8.4. Nothing else in the tree stands out.
