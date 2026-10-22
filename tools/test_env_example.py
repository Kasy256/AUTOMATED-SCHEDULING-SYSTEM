import re
from pathlib import Path

from cartlyf_api.settings import Settings

ENV_EXAMPLE = Path(__file__).resolve().parents[1] / ".env.example"


def test_env_example_lists_every_setting() -> None:
    documented = set(re.findall(r"^#?\s*(CARTLYF_[A-Z0-9_]+)=", ENV_EXAMPLE.read_text(), re.M))
    expected = {f"CARTLYF_{name.upper()}" for name in Settings.model_fields}
    assert sorted(expected - documented) == []
