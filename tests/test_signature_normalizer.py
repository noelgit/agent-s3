import importlib.util
import types
import sys
from pathlib import Path
import copy


def load_signature_normalizer(monkeypatch):
    """Load signature_normalizer module with stubbed dependencies."""
    # Stub plan_validator.validate_code_syntax to avoid heavy imports
    pv_stub = types.ModuleType("agent_s3.tools.plan_validator")
    pv_stub.validate_code_syntax = lambda signature, language=None: True

    # Create minimal package structure
    pkg = types.ModuleType("agent_s3")
    pkg.tools = types.ModuleType("agent_s3.tools")
    monkeypatch.setitem(sys.modules, "agent_s3", pkg)
    monkeypatch.setitem(sys.modules, "agent_s3.tools", pkg.tools)
    monkeypatch.setitem(sys.modules, "agent_s3.tools.plan_validator", pv_stub)

    module_path = Path(__file__).resolve().parents[1] / "agent_s3" / "signature_normalizer.py"
    spec = importlib.util.spec_from_file_location("signature_normalizer", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_normalize_pre_plan_basic(monkeypatch):
    sn_module = load_signature_normalizer(monkeypatch)
    SignatureNormalizer = sn_module.SignatureNormalizer

    pre_plan = {
        "feature_groups": [
            {
                "group_name": "Group A",
                "features": [
                    {
                        "name": "AwesomeFeature",
                        "system_design": {
                            "code_elements": [
                                {
                                    "name": "FirstFunc",
                                    "element_type": "function",
                                    "element_id": "FirstID!",
                                    "target_file": "src/Utilities/FirstFunc.py",
                                    "signature": "def FirstFunc(arg)"
                                },
                                {
                                    "name": "SecondFunc",
                                    "element_type": "function",
                                    "signature": "",
                                    "target_file": "",
                                    "element_id": ""
                                }
                            ]
                        },
                        "test_requirements": {
                            "unit_tests": [
                                {"target_element": "FirstFunc"},
                                {"target_element": "SecondFunc"}
                            ]
                        }
                    }
                ]
            }
        ]
    }

    normalizer = SignatureNormalizer(".")
    result = normalizer.normalize_pre_plan(copy.deepcopy(pre_plan))

    elems = result["feature_groups"][0]["features"][0]["system_design"]["code_elements"]
    first, second = elems[0], elems[1]

    assert first["element_id"] == "firstid_"
    assert first["target_file"].endswith("first_func.py")
    assert first["signature"].endswith(":")

    assert second["element_id"].startswith("awesomefeature_secondfunc_function")
    assert second["target_file"] == "src/secondfunc.py"
    assert second["signature"] == "def SecondFunc():"

    unit_tests = result["feature_groups"][0]["features"][0]["test_requirements"]["unit_tests"]
    assert unit_tests[0]["target_element_id"] == first["element_id"]
    assert unit_tests[1]["target_element_id"] == second["element_id"]


def test_normalize_element_id_uniqueness(monkeypatch):
    sn_module = load_signature_normalizer(monkeypatch)
    SignatureNormalizer = sn_module.SignatureNormalizer

    pre_plan = {
        "feature_groups": [
            {
                "group_name": "G",
                "features": [
                    {
                        "name": "FeatureA",
                        "system_design": {
                            "code_elements": [
                                {"name": "Func", "element_type": "function"},
                                {"name": "Func", "element_type": "function"}
                            ]
                        }
                    }
                ]
            }
        ]
    }

    normalizer = SignatureNormalizer(".")
    result = normalizer.normalize_pre_plan(copy.deepcopy(pre_plan))
    elems = result["feature_groups"][0]["features"][0]["system_design"]["code_elements"]

    assert elems[0]["element_id"] == "featurea_func_function"
    assert elems[1]["element_id"] == "featurea_func_function_1"

