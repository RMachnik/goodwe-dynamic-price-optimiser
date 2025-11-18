This repository implements an energy management system (GoodWe Dynamic Price Optimiser).
The guidance below is focused and actionable for an AI coding agent to make correct, minimal, and maintainable changes.

**Big Picture**
- **Purpose**: Optimize battery charging/discharging based on market prices, PV production, and safety constraints.
- **Architecture**: Hexagonal (Port & Adapter). Business logic lives in `src/` (decision engines), hardware integrations are adapters (inverter adapters) behind `InverterPort`-style interfaces. Central orchestrator: `src/master_coordinator.py` / `config/master_coordinator_config.yaml`.
- **Data flow**: `EnhancedDataCollector` → decision engines (`automated_price_charging.py`, `battery_selling_engine.py`, etc.) → `GoodWeFastCharger` (adapter) → inverter actions. Config drives most runtime behavior via `config/master_coordinator_config.yaml`.

**Where to look first (quick tour)**
- **Core orchestrator & config**: `config/master_coordinator_config.yaml`, `src/master_coordinator.py`, `run_master_coordinator.sh`.
- **Charging logic**: `src/automated_price_charging.py`, `src/enhanced_aggressive_charging.py`, `src/tariff_pricing.py`.
- **Selling logic**: `src/battery_selling_engine.py`, `src/battery_selling_timing.py`.
- **Inverter adapters**: search for modules that import `goodwe` or implement `FastCharger` / `Inverter` wrappers (e.g., `src/fast_charge.py`).
- **Data collection & historic storage**: `src/enhanced_data_collector.py` and `out/energy_data` + `data/energy_data`.
- **Docs**: `docs/` contains design rationale and feature guides (e.g., `INVERTER_ABSTRACTION.md`, `DOCKER_DEPLOYMENT.md`).

**Developer workflows (commands and examples)**
- **Run unit tests**: repository uses `pytest`. Example used in CI/local debugging:
  - `python -m pytest --tb=no -q test/test_database_infrastructure.py::TestStorageInterface::test_batch_operations`
- **Run full test suite**: `python -m pytest -q` (use a venv matching `requirements.txt`).
- **Run locally (simple Docker)**:
  - `docker compose -f docker-compose.simple.yml up --build`
  - Or use helper script: `./scripts/docker_manage.sh build` and `./scripts/docker_manage.sh start`.
- **Run coordinator locally (dev)**:
  - `./run_master_coordinator.sh` or run `src/master_coordinator.py` directly (ensure `config/master_coordinator_config.yaml` is available).

**Project-specific conventions & gotchas**
- **Config-first behavior**: Most modules load defaults from `config/master_coordinator_config.yaml`. When changing behavior, prefer updating config keys and defaults in the config file, and keep runtime code defensive when keys are missing.
- **Hexagonal/adapter pattern**: Keep hardware-specific code inside adapter modules. Business logic functions should accept interfaces or plain data, not hardware clients.
- **Tests and optional imports**: Many modules import optional components (e.g. `goodwe`, forecast collectors). Code often wraps these imports in try/except and degrades gracefully. When adding tests, mock those optional imports.
- **File-based historic storage**: Current storage is file-based (see `data/` and `out/energy_data`). There is scaffolding for future DBs; if you add DB code, keep it behind `data_storage.database_storage` flags in config.
- **Logging & location**: Default runtime log file path is defined in config (`logging.file` defaults to `/opt/...`). For local dev override config to write to `logs/`.

**What AI agents should do when making changes**
- **Small, focused edits**: Prefer minimal changes that fix the root cause. Avoid changing global flow unless necessary.
- **Keep adapters isolated**: Changes to hardware adapters must not alter business logic signatures. If you must change an interface, update all adapters and add tests.
- **Update docs**: When behavior/config defaults change, update the relevant `docs/` page and `config/master_coordinator_config.yaml` comments.
- **Run tests**: After code changes run `pytest` (or targeted tests) and fix any failures. Use the example test invocation above for focused runs.

**Integration points & external dependencies**
- **GoodWe library**: `goodwe` (see `requirements.txt`). Adapters call into this; ensure it is installed in integration and CI environments.
- **Price APIs**: code uses `https://api.raporty.pse.pl/api/csdac-pln` and optional PSE forecast collectors. Network calls should be mocked in unit tests.
- **Docker**: production & dev `docker-compose*.yml` + `Dockerfile`. Use `docker-compose.simple.yml` for quicker local iterations.
- **Systemd**: `systemd/` contains service unit(s) — update carefully for deploy changes.

**Examples to copy when implementing features**
- Add config keys: follow style/placement in `config/master_coordinator_config.yaml` (wide comments + nested sections).
- Add new adapter: mirror structure and defensive import patterns found in `src/fast_charge.py` and `src/battery_selling_engine.py`.
- Add tests: place under `test/` and follow existing naming patterns; use `pytest` fixtures for config and mock hardware.

If anything here is unclear or you want me to expand a section (e.g., list of key files, sample test fixtures, or a template for adding an adapter), tell me which part to expand and I will iterate.
