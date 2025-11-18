# Maintenance Notes

This document records recent repository housekeeping actions and test improvements.

- Disabled Home Assistant `hassfest` validation workflow: this repository is no longer linked to Home Assistant. The workflow at `.github/workflows/hassfest.yaml` has been disabled to prevent unrelated CI failures.
- Consolidated test fixtures: database-related fixtures (`temp_db`, `storage_config`, `storage`) were centralized in `test/conftest.py` to reduce duplication across tests.
- Cleaned up test files: removed script-style test runners and hardened several async tests to be robust across storage implementations.
- Test status: verified locally after these changes — `533 passed, 2 skipped`.

If you want the Home Assistant validation re-enabled in CI, reintroduce the workflow or adapt CI to your preferred validation tools.
