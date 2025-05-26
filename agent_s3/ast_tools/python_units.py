"""
Extract logical units (functions, classes) from Python code using LibCST.
"""
import textwrap
from typing import TYPE_CHECKING

from .parser import parse_python

if TYPE_CHECKING:
    pass

try:
    import libcst
except ImportError:  # pragma: no cover
    libcst = None

if libcst is not None:
    class UnitCollector(libcst.CSTVisitor):
        """Collect top-level function and class definitions."""

        def __init__(self) -> None:
            self.units: list[tuple[str, str, str]] = []

        def visit_FunctionDef(self, node: libcst.FunctionDef) -> None:  # type: ignore[name-defined]
            self.units.append(("function", node.name.value, textwrap.dedent(node.code)))

        def visit_ClassDef(self, node: libcst.ClassDef) -> None:  # type: ignore[name-defined]
            self.units.append(("class", node.name.value, textwrap.dedent(node.code)))
else:  # pragma: no cover - fallback when libcst is unavailable
    class UnitCollector:  # type: ignore
        """Fallback collector used when LibCST is not installed."""

        def __init__(self) -> None:
            self.units: list[tuple[str, str, str]] = []


def extract_units(code: str) -> list[tuple[str, str, str]]:
    """Return top-level classes and functions within the provided code."""
    if libcst is None:
        return []
    mod = parse_python(code)
    collector = UnitCollector()
    mod.visit(collector)
    return collector.units
