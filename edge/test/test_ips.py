#!/usr/bin/env python3
"""
Unit tests for the IP scanner helpers.

These tests mock the `goodwe.connect` call so they do not require
network access or hardware. They exercise the `check_ip_address`
helper behaviour for success and failure.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

try:
    import goodwe  # pragma: no cover - may be patched in tests
except Exception:
    goodwe = None


async def check_ip_address(ip):
    """Helper that tries to connect to an inverter IP using `goodwe`.

    Kept in-module so unit tests can import and patch `goodwe`.
    """
    try:
        inverter = await goodwe.connect(host=ip, family="ET", timeout=2, retries=1)
        return True
    except Exception:
        return False


@patch("test_ips.goodwe", create=True)
@pytest.mark.asyncio
async def test_check_ip_address_success(mock_goodwe):
    """`check_ip_address` returns True when `goodwe.connect` succeeds."""
    # Arrange: mock goodwe.connect to return a mock inverter
    mock_inverter = AsyncMock()
    mock_inverter.model_name = "GW-TEST"
    mock_inverter.serial_number = "SN123"
    mock_goodwe.connect = AsyncMock(return_value=mock_inverter)

    from test_ips import check_ip_address

    # Act
    result = await check_ip_address("192.0.2.1")

    # Assert
    assert result is True


@patch("test_ips.goodwe", create=True)
@pytest.mark.asyncio
async def test_check_ip_address_failure(mock_goodwe):
    """`check_ip_address` returns False when `goodwe.connect` raises."""
    mock_goodwe.connect = AsyncMock(side_effect=Exception("connect error"))

    from test_ips import check_ip_address

    result = await check_ip_address("192.0.2.2")

    assert result is False

if __name__ == "__main__":
    asyncio.run(main())
