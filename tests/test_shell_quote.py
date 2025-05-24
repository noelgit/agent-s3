import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

NODE_SCRIPT = (
    "const { quote } = require('./vscode/shellQuote.js');"
    "const args = JSON.parse(process.argv[1]);"
    "console.log(quote(args));"
)

def run_quote(args):
    result = subprocess.check_output(
        ['node', '-e', NODE_SCRIPT, json.dumps(args)], cwd=REPO_ROOT
    )
    return result.decode().strip()

def test_quote_simple():
    assert run_quote(["simple"]) == "'simple'"

def test_quote_spaces():
    assert run_quote(["hello world"]) == "'hello world'"

def test_quote_single_quote():
    assert run_quote(["O'Reilly"]) == "'O'\\''Reilly'"

