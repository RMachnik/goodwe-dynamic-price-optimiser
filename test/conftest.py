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
import yaml
import pytest
from pathlib import Path as _Path

from database.storage_interface import StorageConfig
from database.sqlite_storage import SQLiteStorage


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
async def storage(storage_config):
	"""Create a SQLiteStorage instance."""
	s = SQLiteStorage(storage_config)
	await s.connect()
	yield s
	await s.disconnect()


@pytest.fixture
def isolated_config():
	"""
	Create an isolated test configuration file with standard test settings.
	
	This fixture provides a temporary YAML configuration file with
	commonly used test settings, ensuring tests don't depend on
	production configuration.
	
	Yields:
		str: Path to temporary config file
		
	Cleanup:
		Automatically removes the config file after test completion
	"""
	test_config = {
		'electricity_pricing': {
			'sc_component_net': 0.0892,
			'sc_component_gross': 0.1097,
			'minimum_price_floor': 0.0050
		},
		'electricity_tariff': {
			'tariff_type': 'g12w',
			'sc_component_pln_kwh': 0.0892,
			'distribution_pricing': {
				'g12w': {
					'type': 'time_based',
					'peak_hours': {'start': 7, 'end': 22},
					'prices': {'peak': 0.3566, 'off_peak': 0.0749}
				}
			}
		},
		'battery_management': {
			'soc_thresholds': {
				'critical': 12,
				'emergency': 5
			}
		},
		'cheapest_price_aggressive_charging': {
			'enabled': True
		}
	}
	
	config_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
	yaml.dump(test_config, config_file)
	config_file.close()
	
	try:
		yield config_file.name
	finally:
		try:
			os.unlink(config_file.name)
		except Exception:
			pass


@pytest.fixture
def custom_config():
	"""
	Fixture that provides a factory function for creating custom test configuration files.
	
	This fixture returns a factory function that creates temporary config files
	with user-specified settings, allowing tests to customize configuration
	as needed. Multiple config files can be created within a single test, and
	all are automatically cleaned up after test completion.
	
	Returns:
		function: Factory function that accepts config dict and returns config path
		
	Example:
		def test_with_custom_config(custom_config):
			config_path = custom_config({
				'electricity_tariff': {'tariff_type': 'g14dynamic'}
			})
			# Use config_path in test...
	"""
	created_files = []
	
	def _create_config(config_dict):
		config_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
		yaml.dump(config_dict, config_file)
		config_file.close()
		created_files.append(config_file.name)
		return config_file.name
	
	yield _create_config
	
	# Cleanup all created files
	for file_path in created_files:
		try:
			os.unlink(file_path)
		except Exception:
			pass

