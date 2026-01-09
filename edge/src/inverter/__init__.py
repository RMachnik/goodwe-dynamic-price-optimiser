"""
Inverter Abstraction Layer

This package provides a vendor-agnostic interface for inverter integration
using the port and adapter pattern (hexagonal architecture).

The abstraction enables support for multiple inverter brands (GoodWe, Fronius, SMA, etc.)
while maintaining a consistent interface for the energy management algorithm.
"""

from .factory.inverter_factory import InverterFactory
from .models.operation_mode import OperationMode
from .models.inverter_config import InverterConfig, SafetyConfig
from .ports.inverter_port import InverterPort

__all__ = [
    'InverterFactory',
    'InverterPort',
    'OperationMode',
    'InverterConfig',
    'SafetyConfig',
]

