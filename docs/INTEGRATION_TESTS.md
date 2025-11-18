Integration tests and hardware/network-dependent tests
===============================================

Overview
--------
Some tests in this repository contact external hardware (GoodWe inverters) or network
services (weather APIs). To keep the main test suite fast and deterministic in CI,
these integration tests are disabled by default and must be opted-in locally.

How to run integration tests
----------------------------
- By default the pytest run will skip integration tests.
- To enable them locally set the environment variable `RUN_EXTERNAL_TESTS=1`.

Example (macOS / zsh):

```bash
# enable and run pytest (may contact hardware and take longer)
RUN_EXTERNAL_TESTS=1 python -m pytest -q
```

Notes
-----
- These tests may require hardware on the local network, the `goodwe` Python
  package, and network access to weather APIs. They may also take longer than
  unit tests and could be flaky if the external hardware is unavailable.
- In CI we recommend keeping them disabled and running them separately on a
  dedicated integration environment with access to the required devices.

If you want, I can add a CI job to run integration tests conditionally (e.g.
when a secret/integration flag is present).
