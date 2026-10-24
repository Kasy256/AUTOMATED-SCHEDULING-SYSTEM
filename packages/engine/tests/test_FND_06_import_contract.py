import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_FND_06_engine_import_contract_holds() -> None:
    lint_imports = shutil.which("lint-imports")
    assert lint_imports, "import-linter is not installed"
    result = subprocess.run(
        [lint_imports], cwd=REPO_ROOT, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr
