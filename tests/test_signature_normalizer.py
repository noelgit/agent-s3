import os
import unittest
from copy import deepcopy
import sys
import types
from pathlib import Path

# Create a lightweight agent_s3 package to avoid heavy side effects from the
# real __init__ which imports optional dependencies.
if 'agent_s3' not in sys.modules:
    pkg = types.ModuleType('agent_s3')
    pkg.__path__ = [str(Path(__file__).resolve().parents[1] / 'agent_s3')]
    sys.modules['agent_s3'] = pkg

# Stub plan_validator to avoid optional dependencies like libcst.
tools_pkg = types.ModuleType('agent_s3.tools')
tools_pkg.__path__ = [str(Path(__file__).resolve().parents[1] / 'agent_s3' / 'tools')]
sys.modules.setdefault('agent_s3.tools', tools_pkg)

plan_validator_stub = types.ModuleType('agent_s3.tools.plan_validator')
plan_validator_stub.validate_code_syntax = lambda *args, **kwargs: True
sys.modules['agent_s3.tools.plan_validator'] = plan_validator_stub

from agent_s3.signature_normalizer import SignatureNormalizer


class TestSignatureNormalizer(unittest.TestCase):
    """Tests for signature normalization utilities."""

    def setUp(self):
        self.normalizer = SignatureNormalizer(cwd=".")

    def test_normalize_pre_plan_basic(self):
        pre_plan = {
            "feature_groups": [
                {
                    "group_name": "Group1",
                    "features": [
                        {
                            "name": "LoginFeature",
                            "description": "desc",
                            "files_affected": [],
                            "dependencies": {},
                            "risk_assessment": {},
                            "system_design": {
                                "code_elements": [
                                    {
                                        "element_type": "class",
                                        "name": "AuthManager",
                                        "element_id": "",
                                        "target_file": "src/AuthManager.py",
                                        "signature": "class AuthManager",
                                        "description": "",
                                        "key_attributes_or_methods": [],
                                    },
                                    {
                                        "element_type": "function",
                                        "name": "helper_func",
                                        "element_id": "",
                                        "target_file": "",
                                        "signature": "",
                                        "description": "",
                                        "key_attributes_or_methods": [],
                                    },
                                    {
                                        "element_type": "function",
                                        "name": "doThing",
                                        "element_id": "",
                                        "target_file": "src/do_thing.ts",
                                        "signature": "function doThing()",
                                        "description": "",
                                        "key_attributes_or_methods": [],
                                    },
                                ]
                            },
                            "test_requirements": {
                                "unit_tests": [
                                    {"description": "t", "target_element": "AuthManager"}
                                ],
                                "integration_tests": []
                            },
                        }
                    ],
                }
            ]
        }

        normalized = self.normalizer.normalize_pre_plan(deepcopy(pre_plan))
        element = normalized["feature_groups"][0]["features"][0]["system_design"]["code_elements"][0]
        self.assertEqual(element["element_id"], "loginfeature_authmanager_class")
        self.assertEqual(element["target_file"], os.path.normpath("src/auth_manager.py"))
        self.assertEqual(element["signature"], "class AuthManager():")

        # second element checks default file and signature generation
        second = normalized["feature_groups"][0]["features"][0]["system_design"]["code_elements"][1]
        self.assertEqual(second["target_file"], os.path.normpath("src/helper_func.py"))
        self.assertEqual(second["signature"], "def helper_func():")

        # third element checks js/ts handling
        third = normalized["feature_groups"][0]["features"][0]["system_design"]["code_elements"][2]
        self.assertEqual(third["target_file"], os.path.normpath("src/doThing.ts"))
        self.assertEqual(third["signature"], "function doThing();")

        # test requirement updated with element id
        unit_test = normalized["feature_groups"][0]["features"][0]["test_requirements"]["unit_tests"][0]
        self.assertEqual(unit_test.get("target_element_id"), element["element_id"])

    def test_element_id_uniqueness(self):
        id1 = self.normalizer._normalize_element_id("duplicate", "Name", "function", "Feat", "Group")
        id2 = self.normalizer._normalize_element_id("duplicate", "Name", "function", "Feat", "Group")
        self.assertEqual(id1, "duplicate")
        self.assertEqual(id2, "duplicate_1")


if __name__ == "__main__":
    unittest.main()
