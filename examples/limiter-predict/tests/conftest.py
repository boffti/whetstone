"""Predict by reading: solution.py may not import the code it predicts, on Run or on Submit."""

import sys
from pathlib import Path

import pytest

# Every module next to solution.py is code under study (the question's support files).
SUBJECTS = [p.stem for p in Path(__file__).resolve().parent.parent.glob("*.py") if p.stem != "solution"]


@pytest.fixture(autouse=True, scope="session")
def predictions_come_from_reading():
    """Import solution.py again with the subjects blocked: None in sys.modules makes `import subject` fail."""
    kept = {name: sys.modules.get(name) for name in SUBJECTS}
    sys.modules.update(dict.fromkeys(SUBJECTS))
    sys.modules.pop("solution", None)
    try:
        import solution

        getattr(solution, "ANSWERS", None)  # a module __getattr__ that runs the code counts too
    except ImportError:
        pytest.fail("solution.py runs the code it should predict. Read it, write the value, and leave the import out.", pytrace=False)
    finally:
        for name, module in kept.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
