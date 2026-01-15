import pytest
import yaml
from src.master_coordinator import MasterCoordinator, deep_merge

def test_deep_merge():
    base = {"a": 1, "b": {"c": 2}}
    override = {"b": {"c": 3, "d": 4}, "e": 5}
    result = deep_merge(base, override)
    assert result == {"a": 1, "b": {"c": 3, "d": 4}, "e": 5}

def test_layered_config_loading(tmp_path):
    # Setup paths
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    
    # MasterCoordinator uses name.replace('.yaml', '_local.yaml')
    # If config_path is master_coordinator_config.yaml, local is master_coordinator_config_local.yaml
    base_file = config_dir / "master_coordinator_config.yaml"
    local_file = config_dir / "master_coordinator_config_local.yaml"
    override_file = config_dir / "override_config.yaml"
    
    # Layer 1: Base
    base_data = {
        "inverter": {"ip": "1.1.1.1"},
        "battery": {"capacity": 10},
        "other": "base"
    }
    with open(base_file, 'w') as f:
        yaml.dump(base_data, f)
        
    # Layer 2: Local (Hardware)
    local_data = {
        "inverter": {"ip": "2.2.2.2"}
    }
    with open(local_file, 'w') as f:
        yaml.dump(local_data, f)
        
    # Layer 3: Override (Cloud)
    override_data = {
        "battery": {"capacity": 20}
    }
    with open(override_file, 'w') as f:
        yaml.dump(override_data, f)
        
    coordinator = MasterCoordinator(config_path=str(base_file))
    coordinator.storage = None # Bypassing DB during tests
    config = coordinator._load_config()
    
    assert config["inverter"]["ip"] == "2.2.2.2"  # From Local
    assert config["battery"]["capacity"] == 20   # From Override
    assert config["other"] == "base"             # From Base

def test_config_bootstrapping(tmp_path):
    # Setup paths
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    
    base_file = config_dir / "master_coordinator_config.yaml"
    expected_local_file = config_dir / "master_coordinator_config_local.yaml"
    
    # Layer 1: Base with hardware info
    base_data = {
        "inverter": {"ip": "1.1.1.1", "port": 8899},
        "battery_management": {"capacity_kwh": 20.0}
    }
    with open(base_file, 'w') as f:
        yaml.dump(base_data, f)
        
    assert not expected_local_file.exists()
    
    coordinator = MasterCoordinator(config_path=str(base_file))
    coordinator.storage = None
    coordinator._load_config()
    
    # Check if local file was created
    assert expected_local_file.exists()
    with open(expected_local_file, 'r') as f:
        bootstrapped = yaml.safe_load(f)
        
    assert bootstrapped["inverter"]["ip"] == "1.1.1.1"
    assert bootstrapped["battery_management"]["capacity_kwh"] == 20.0
