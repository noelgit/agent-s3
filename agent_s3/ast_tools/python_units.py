"""
Extract logical units (functions, classes) from Python code using LibCST.
"""
import libcst
import textwrap
from .parser import parse_python

class UnitCollector(libcst.CSTVisitor):
    def __init__(self):
        self.units = []
    def visit_FunctionDef(self, node):
        self.units.append(("function", node.name.value, textwrap.dedent(node.code)))
    def visit_ClassDef(self, node):
        self.units.append(("class", node.name.value, textwrap.dedent(node.code)))

def extract_units(code: str):
    mod = parse_python(code)
    collector = UnitCollector()
    mod.visit(collector)
    return collector.units
