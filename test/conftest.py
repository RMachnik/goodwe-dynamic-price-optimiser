"""
conftest.py

This file intentionally left minimal. We previously attempted to patch
unittest.TestCase to await coroutine test methods, but that changed test
semantics and caused failures. Suppress warnings using `pytest.ini` instead.
"""

__all__ = []
