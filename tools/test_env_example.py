import re
from pathlib import Path

from cartlyf_api.settings import Settings

ENV_EXAMPLE = Path(__file__).resolve().parents[1] / ".env.example"


def test_env_example_lists_every_setting() -> None:
    documented = set(re.findall(r"^#?\s*(CARTLYF_[A-Z0-9_]+)=", ENV_EXAMPLE.read_text(), re.M))
    # Fields read from a platform variable (an alias without our prefix) are not ours to document.
    expected = {
        f"CARTLYF_{name.upper()}"
        for name, field in Settings.model_fields.items()
        if not isinstance(field.validation_alias, str)
    }
    assert sorted(expected - documented) == []
