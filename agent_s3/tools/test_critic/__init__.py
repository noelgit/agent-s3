"""
TestCritic module for test quality assessment and TDD workflow.

Provides both static analysis of test quality and actual test execution
as part of the TDD/ATDD workflow.
"""

from .core import TestCritic, TestType, TestVerdict, select_adapter
from .adapters.base import Adapter
from . import adapters, reporter

__all__ = [
    'TestCritic',
    'TestType',
    'TestVerdict',
    'select_adapter',
    'Adapter',
    'adapters',
    'reporter'
]
