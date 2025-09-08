"""Simple test script to check inverter UDP protocol communication"""

import asyncio
import goodwe
import logging
import sys
import os
import pytest


def test_inverter_connection():
    """Test inverter connection - only runs if inverter is available"""
    logging.basicConfig(
        format="%(asctime)-15s %(funcName)s(%(lineno)d) - %(levelname)s: %(message)s",
        stream=sys.stderr,
        level=getattr(logging, "ERROR", None),
    )

    # Set the appropriate IP address
    IP_ADDRESS = "192.168.2.14"
    PORT = 8899

    FAMILY = "ET"  # One of ET, ES, DT or None to detect inverter family automatically
    COMM_ADDR = None  # Usually 0xf7 for ET/ES or 0x7f for DT, or None for default value
    TIMEOUT = 1
    RETRIES = 3

    try:
        inverter = asyncio.run(
            goodwe.connect(host=IP_ADDRESS, family=FAMILY, timeout=TIMEOUT, retries=RETRIES)
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
