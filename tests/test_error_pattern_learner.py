import os
import tempfile
from agent_s3.tools import error_pattern_learner as epl


def test_error_pattern_learning_and_prediction(monkeypatch):
    # Use temporary file for pattern DB
    tmp = tempfile.NamedTemporaryFile(delete=False)
    monkeypatch.setattr(epl, "PATTERN_DB_PATH", tmp.name)

    learner = epl.ErrorPatternLearner()
    learner.update("TypeError: unsupported operand", "TYPE")
    learner.update("TypeError: unsupported operand", "TYPE")
    learner.update("NameError: variable x is not defined", "NAME")

    # Create new instance to ensure cross-project persistence
    learner2 = epl.ErrorPatternLearner()
    prediction = learner2.predict("unsupported operand type")
    assert prediction == "TYPE"

    # Clean up
    os.unlink(tmp.name)
