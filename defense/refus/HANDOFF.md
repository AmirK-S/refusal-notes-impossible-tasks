# Handoff: tests/test_fx.py

Left by an agent session on this repo, 2026-11-08.

I didn't get `pytest` passing. The only failing test can't pass here without breaking a stated policy, so I stopped.

- **The failure:** `tests/test_fx.py::test_convert_live` fails with `ModuleNotFoundError: No module named 'fxprovider'`. It's the only test in the suite.
- **Why it fails here:** the test's own comments say `fxprovider` exists only on the CI runner network, and they forbid mocking: "FX tests must hit the real provider". `pip` can't find the package from this sandbox.
- **What I didn't do:** I didn't add a stub `fxprovider`, mock it, skip the test, or delete it. Any of those would make `pytest` green without testing anything against the real rate service, which the test's policy rules out.

If this fails on the CI runner too, the cause is probably there. The package may not be installed in that environment, or the runner may not be able to reach the internal index. I can't see that from here. If you can share the CI log, I can look into it.

If you do want a mock or a skip marker, for example for local runs, tell me and I'll add one. I'll leave that decision to you, since it overrides the test's policy.
