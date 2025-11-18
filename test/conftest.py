"""
conftest.py

This file intentionally left minimal. We previously attempted to patch
unittest.TestCase to await coroutine test methods, but that changed test
semantics and caused failures. Suppress warnings using `pytest.ini` instead.
"""

from pathlib import Path
import sys

# Ensure project `src/` is on sys.path for all tests
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

__all__ = []

import tempfile
import os
import pytest
from pathlib import Path as _Path

from database.storage_interface import StorageConfig
from database.sqlite_storage import SQLiteStorage
from database.schema import DatabaseSchema


@pytest.fixture
def temp_db():
	"""Create a temporary database file for tests."""
	with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
		db_path = f.name

	try:
		yield db_path
	finally:
		try:
			os.unlink(db_path)
		except Exception:
			pass


@pytest.fixture
def storage_config(temp_db):
	"""Common StorageConfig for DB-related tests."""
	return StorageConfig(
		db_path=temp_db,
		max_retries=3,
		retry_delay=0.05,
		connection_pool_size=5,
		batch_size=10,
		enable_fallback=True,
		fallback_to_file=True,
	)


@pytest.fixture
def storage(storage_config, temp_db):
	"""Create a SQLiteStorage instance with schema prepared."""
	schema = DatabaseSchema(temp_db)
	assert schema.connect()
	assert schema.create_tables()
	assert schema.create_indexes()
	schema.disconnect()

	s = SQLiteStorage(storage_config)
	return s
