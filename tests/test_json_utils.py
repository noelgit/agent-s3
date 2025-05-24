from agent_s3.json_utils import repair_json_structure
from agent_s3.json_utils import validate_json_against_schema

def test_repair_json_structure_nested_arrays():
    schema = {
        "items": [
            {
                "name": str,
                "values": [int],
            }
        ]
    }

    data = {
        "items": [
            {"name": "foo", "values": [1, "2", 3]},
            {"values": "not list"},
            "invalid",
        ]
    }

    repaired = repair_json_structure(data, schema)

    assert len(repaired["items"]) == 3
    assert repaired["items"][0]["values"][1] == 0
    assert repaired["items"][1]["name"] == ""
    assert repaired["items"][1]["values"] == []
    assert repaired["items"][2]["values"] == []

    valid, errors = validate_json_against_schema(repaired, schema)
    assert valid, f"Unexpected errors: {errors}"


def test_repair_json_structure_multi_dimensional_array():
    schema = {"matrix": [[int]]}

    data = {"matrix": [[1, 2], [3, "4"], "bad", [True]]}

    repaired = repair_json_structure(data, schema)

    assert repaired["matrix"][1][1] == 0
    assert repaired["matrix"][2] == []
    assert repaired["matrix"][3][0] == 0

    valid, errors = validate_json_against_schema(repaired, schema)
    assert valid, f"Unexpected errors: {errors}"
