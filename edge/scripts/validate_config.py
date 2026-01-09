#!/usr/bin/env python3
"""
Configuration Validation Script for GoodWe Dynamic Price Optimiser

This script validates the master_coordinator_config.yaml file to ensure:
1. Valid YAML syntax
2. Required sections exist
3. Required properties within sections exist
4. Data types are correct (numbers, booleans, strings, etc.)
5. Value ranges are valid
6. No deprecated properties are used

Usage:
    python scripts/validate_config.py [config_file_path]

If no path provided, defaults to config/master_coordinator_config.yaml
"""

import sys
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ANSI color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

# Schema definition for master_coordinator_config.yaml
CONFIG_SCHEMA = {
    "inverter": {
        "required": True,
        "properties": {
            "vendor": {"type": str, "required": True},
            "ip_address": {"type": str, "required": True},
            "port": {"type": int, "required": True, "min": 1, "max": 65535},
            "timeout": {"type": (int, float), "required": True, "min": 0.1},
            "retries": {"type": int, "required": True, "min": 0},
            "retry_delay": {"type": (int, float), "required": True, "min": 0},
            "family": {"type": (str, type(None)), "required": False},
            "comm_addr": {"type": int, "required": False},
        }
    },
    "charging": {
        "required": True,
        "properties": {
            "max_power": {"type": int, "required": True, "min": 0},
            "safety_voltage_min": {"type": (int, float), "required": True, "min": 0},
            "safety_voltage_max": {"type": (int, float), "required": True, "min": 0},
            "safety_current_max": {"type": (int, float), "required": True, "min": 0},
            "safety_temp_max": {"type": (int, float), "required": True, "min": -50, "max": 100},
            "safety_temp_min": {"type": (int, float), "required": True, "min": -50, "max": 100},
        }
    },
    "electricity_tariff": {
        "required": True,
        "properties": {
            "tariff_type": {"type": str, "required": True, "choices": ["g11", "g12", "g12as", "g12w", "g13", "g13s", "g14dynamic"]},
            "sc_component_pln_kwh": {"type": (int, float), "required": True, "min": 0},
        }
    },
    "coordinator": {
        "required": True,
        "properties": {
            "decision_interval_minutes": {"type": int, "required": True, "min": 1},
            "health_check_interval_minutes": {"type": int, "required": True, "min": 1},
            "data_collection_interval_seconds": {"type": int, "required": True, "min": 1},
            "data_retention_days": {"type": int, "required": True, "min": 1},
        }
    },
    "battery_management": {
        "required": True,
        "properties": {
            "capacity_kwh": {"type": (int, float), "required": True, "min": 0},
            "battery_type": {"type": str, "required": True},
            "soc_thresholds": {"type": dict, "required": True},
        }
    },
    "logging": {
        "required": True,
        "properties": {
            "level": {"type": str, "required": True, "choices": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]},
            "file": {"type": str, "required": True},
        }
    },
    "data_storage": {
        "required": True,
        "properties": {
            "file_storage": {"type": dict, "required": True},
        }
    },
    "weather_integration": {
        "required": True,
        "properties": {
            "enabled": {"type": bool, "required": True},
        }
    },
    "timing_awareness": {
        "required": True,
        "properties": {
            "enabled": {"type": bool, "required": True},
            "smart_critical_charging": {"type": dict, "required": True},
        }
    },
    "battery_selling": {
        "required": True,
        "properties": {
            "enabled": {"type": bool, "required": True},
            "min_battery_soc": {"type": (int, float), "required": True, "min": 0, "max": 100},
        }
    }
}

# Deprecated properties that should not be present
DEPRECATED_PROPERTIES = {
    "coordinator.decision_weights": "Removed: never referenced in code",
    "coordinator.charging_thresholds": "Removed: never referenced in code",
    "performance_monitoring": "Removed: entire section unused",
    "notifications": "Removed: entire section per user request",
    "pv_monitoring": "Removed: never referenced in code",
    "grid_flow": "Removed: never referenced in code",
    "consumption_monitoring": "Removed: never referenced in code",
    "data_storage.file_storage.compression": "Removed: never referenced in code",
    "data_storage.file_storage.backup_interval_hours": "Removed: never referenced in code",
    "logging.console_output": "Removed: never referenced in code",
    "logging.log_to_file": "Removed: never referenced in code",
    "logging.max_file_size": "Removed: never referenced in code",
    "logging.backup_count": "Removed: never referenced in code",
    "debug": "Removed: entire section unused",
    "battery_selling.monitoring": "Removed: never referenced in code",
    "battery_selling.expected_daily_revenue_pln": "Removed: documentation-only property",
    "battery_selling.expected_monthly_revenue_pln": "Removed: documentation-only property",
    "battery_selling.expected_annual_revenue_pln": "Removed: documentation-only property",
    "cheapest_price_aggressive_charging.override_pv_overproduction": "Removed: never referenced in code",
    "cheapest_price_aggressive_charging.min_charging_duration_minutes": "Removed: never referenced in code",
    "cheapest_price_aggressive_charging.max_price_difference_pln": "Removed: use price_threshold_percent instead",
}


def load_yaml_file(file_path: Path) -> Tuple[Optional[Dict], List[str]]:
    """Load and parse YAML file, return (config, errors)"""
    errors = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            if not isinstance(config, dict):
                errors.append(f"Config file must contain a dictionary, got {type(config).__name__}")
                return None, errors
            return config, errors
    except FileNotFoundError:
        errors.append(f"Config file not found: {file_path}")
        return None, errors
    except yaml.YAMLError as e:
        errors.append(f"YAML syntax error: {e}")
        return None, errors
    except Exception as e:
        errors.append(f"Failed to load config: {e}")
        return None, errors


def validate_type(value: Any, expected_types: tuple, property_path: str) -> Optional[str]:
    """Validate value type, return error message if invalid"""
    if not isinstance(value, expected_types):
        expected_names = " or ".join([t.__name__ for t in (expected_types if isinstance(expected_types, tuple) else (expected_types,))])
        return f"{property_path}: Expected type {expected_names}, got {type(value).__name__}"
    return None


def validate_range(value: Any, min_val: Optional[float], max_val: Optional[float], property_path: str) -> Optional[str]:
    """Validate numeric range, return error message if invalid"""
    if min_val is not None and value < min_val:
        return f"{property_path}: Value {value} is below minimum {min_val}"
    if max_val is not None and value > max_val:
        return f"{property_path}: Value {value} exceeds maximum {max_val}"
    return None


def validate_choices(value: Any, choices: List, property_path: str) -> Optional[str]:
    """Validate value is in allowed choices, return error message if invalid"""
    if value not in choices:
        return f"{property_path}: Value '{value}' not in allowed choices: {choices}"
    return None


def validate_section(config: Dict, section_name: str, schema: Dict, errors: List[str], warnings: List[str]):
    """Validate a config section against its schema"""
    section_schema = schema.get(section_name)
    if not section_schema:
        return
    
    # Check if section is required
    if section_schema.get("required") and section_name not in config:
        errors.append(f"Required section '{section_name}' is missing")
        return
    
    if section_name not in config:
        return
    
    section = config[section_name]
    if not isinstance(section, dict):
        errors.append(f"Section '{section_name}' must be a dictionary, got {type(section).__name__}")
        return
    
    # Validate properties
    properties = section_schema.get("properties", {})
    for prop_name, prop_schema in properties.items():
        property_path = f"{section_name}.{prop_name}"
        
        # Check if property is required
        if prop_schema.get("required") and prop_name not in section:
            errors.append(f"Required property '{property_path}' is missing")
            continue
        
        if prop_name not in section:
            continue
        
        value = section[prop_name]
        
        # Validate type
        expected_types = prop_schema["type"]
        if not isinstance(expected_types, tuple):
            expected_types = (expected_types,)
        
        error = validate_type(value, expected_types, property_path)
        if error:
            errors.append(error)
            continue
        
        # Validate range for numeric types
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            min_val = prop_schema.get("min")
            max_val = prop_schema.get("max")
            error = validate_range(value, min_val, max_val, property_path)
            if error:
                errors.append(error)
        
        # Validate choices
        if "choices" in prop_schema:
            error = validate_choices(value, prop_schema["choices"], property_path)
            if error:
                errors.append(error)


def check_deprecated_properties(config: Dict, deprecated: Dict, warnings: List[str], path: str = ""):
    """Recursively check for deprecated properties"""
    for key, value in config.items():
        current_path = f"{path}.{key}" if path else key
        
        # Check if this path is deprecated
        if current_path in deprecated:
            warnings.append(f"Deprecated property '{current_path}': {deprecated[current_path]}")
        
        # Recursively check nested dictionaries
        if isinstance(value, dict):
            check_deprecated_properties(value, deprecated, warnings, current_path)


def validate_custom_rules(config: Dict, errors: List[str], warnings: List[str]):
    """Apply custom validation rules"""
    
    # Rule 1: safety_voltage_max must be greater than safety_voltage_min
    if "charging" in config:
        charging = config["charging"]
        if "safety_voltage_min" in charging and "safety_voltage_max" in charging:
            if charging["safety_voltage_max"] <= charging["safety_voltage_min"]:
                errors.append("charging.safety_voltage_max must be greater than safety_voltage_min")
    
    # Rule 2: safety_temp_max must be greater than safety_temp_min
    if "charging" in config:
        charging = config["charging"]
        if "safety_temp_min" in charging and "safety_temp_max" in charging:
            if charging["safety_temp_max"] <= charging["safety_temp_min"]:
                errors.append("charging.safety_temp_max must be greater than safety_temp_min")
    
    # Rule 3: battery_management SOC thresholds should be ordered
    if "battery_management" in config:
        battery = config["battery_management"]
        if "soc_thresholds" in battery:
            thresholds = battery["soc_thresholds"]
            if all(k in thresholds for k in ["emergency", "critical", "low", "medium", "high"]):
                if not (thresholds["emergency"] < thresholds["critical"] < thresholds["low"] < 
                       thresholds["medium"] < thresholds["high"]):
                    warnings.append("battery_management.soc_thresholds: Consider ordering emergency < critical < low < medium < high")
    
    # Rule 4: coordinator intervals should be reasonable
    if "coordinator" in config:
        coord = config["coordinator"]
        if "decision_interval_minutes" in coord:
            if coord["decision_interval_minutes"] < 5:
                warnings.append("coordinator.decision_interval_minutes < 5: May cause excessive API calls")
        if "data_collection_interval_seconds" in coord:
            if coord["data_collection_interval_seconds"] < 30:
                warnings.append("coordinator.data_collection_interval_seconds < 30: May cause excessive inverter queries")


def print_results(errors: List[str], warnings: List[str], config_path: Path):
    """Print validation results with colors"""
    print(f"\n{Colors.BOLD}Config Validation Report: {config_path}{Colors.END}\n")
    print("=" * 80)
    
    if errors:
        print(f"\n{Colors.RED}{Colors.BOLD}❌ ERRORS ({len(errors)}):{Colors.END}")
        for i, error in enumerate(errors, 1):
            print(f"  {i}. {error}")
    
    if warnings:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠️  WARNINGS ({len(warnings)}):{Colors.END}")
        for i, warning in enumerate(warnings, 1):
            print(f"  {i}. {warning}")
    
    print("\n" + "=" * 80)
    
    if not errors and not warnings:
        print(f"{Colors.GREEN}{Colors.BOLD}✓ Configuration is valid!{Colors.END}\n")
        return 0
    elif not errors:
        print(f"{Colors.YELLOW}{Colors.BOLD}⚠️  Configuration is valid but has warnings{Colors.END}\n")
        return 0
    else:
        print(f"{Colors.RED}{Colors.BOLD}❌ Configuration has errors and must be fixed{Colors.END}\n")
        return 1


def main():
    """Main validation entry point"""
    # Determine config file path
    if len(sys.argv) > 1:
        config_path = Path(sys.argv[1])
    else:
        # Default to config/master_coordinator_config.yaml relative to script
        script_dir = Path(__file__).parent
        config_path = script_dir.parent / "config" / "master_coordinator_config.yaml"
    
    print(f"\n{Colors.BLUE}Validating config: {config_path}{Colors.END}")
    
    # Load config
    config, errors = load_yaml_file(config_path)
    if config is None:
        print_results(errors, [], config_path)
        return 1
    
    warnings = []
    
    # Validate required sections
    for section_name in CONFIG_SCHEMA:
        validate_section(config, section_name, CONFIG_SCHEMA, errors, warnings)
    
    # Check for deprecated properties
    check_deprecated_properties(config, DEPRECATED_PROPERTIES, warnings)
    
    # Apply custom validation rules
    validate_custom_rules(config, errors, warnings)
    
    # Print results
    return print_results(errors, warnings, config_path)


if __name__ == "__main__":
    sys.exit(main())
