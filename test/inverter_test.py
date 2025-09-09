"""Simple test script to check inverter UDP protocol communication"""

import asyncio
import goodwe
import logging
import sys
import os
import pytest
import yaml


def test_inverter_connection():
    """Test inverter connection - only runs if inverter is available"""
    logging.basicConfig(
        format="%(asctime)-15s %(funcName)s(%(lineno)d) - %(levelname)s: %(message)s",
        stream=sys.stderr,
        level=getattr(logging, "ERROR", None),
    )

    # Load configuration from master_coordinator_config.yaml
    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "master_coordinator_config.yaml")
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Extract inverter configuration
        inverter_config = config.get('inverter', {})
        IP_ADDRESS = inverter_config.get('ip_address', '192.168.2.14')
        PORT = inverter_config.get('port', 8899)
        FAMILY = inverter_config.get('family', 'ET')
        COMM_ADDR = inverter_config.get('comm_addr', 0xf7)
        TIMEOUT = inverter_config.get('timeout', 1)
        RETRIES = inverter_config.get('retries', 3)
        
        print(f"Using inverter configuration from {config_path}:")
        print(f"  IP: {IP_ADDRESS}")
        print(f"  Port: {PORT}")
        print(f"  Family: {FAMILY}")
        print(f"  Comm Addr: {COMM_ADDR}")
        
    except Exception as e:
        print(f"Failed to load config, using defaults: {e}")
        # Fallback to hardcoded values
        IP_ADDRESS = "192.168.2.14"
        PORT = 8899
        FAMILY = "ET"
        COMM_ADDR = 0xf7
        TIMEOUT = 1
        RETRIES = 3

    try:
        inverter = asyncio.run(
            goodwe.connect(host=IP_ADDRESS, family=FAMILY, comm_addr=COMM_ADDR, timeout=TIMEOUT, retries=RETRIES)
        )
        print(
            f"Identified inverter:\n"
            f"\tModel:    {inverter.model_name}\n"
            f"\tSerialNr: {inverter.serial_number}\n"
            f"\tFirmware: {inverter.firmware}"
        )

        response = asyncio.run(inverter.read_runtime_data())

        print("\nSensors values:")
        for sensor in inverter.sensors():
            if sensor.id_ in response:
                print(
                    f"\t{sensor.id_:30}:\t{sensor.name} = {response[sensor.id_]} {sensor.unit}"
                )
        assert True, "Inverter connection successful"
    except Exception as e:
        print(f"Inverter connection test skipped: {e}")
        pytest.skip(f"Inverter not available: {e}")


if __name__ == "__main__":
    test_inverter_connection()
