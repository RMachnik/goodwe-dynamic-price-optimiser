"""
Port Interfaces for Inverter Abstraction Layer.

These interfaces define the contracts that adapter implementations must fulfill.
Using the port and adapter pattern, these ports represent the application's
needs, while adapters translate between ports and vendor-specific implementations.
"""

from .inverter_port import InverterPort
from .command_executor_port import CommandExecutorPort
from .data_collector_port import DataCollectorPort, PVData, GridData, ConsumptionData, ComprehensiveData

__all__ = [
    'InverterPort',
    'CommandExecutorPort',
    'DataCollectorPort',
    'PVData',
    'GridData',
    'ConsumptionData',
    'ComprehensiveData',
]

