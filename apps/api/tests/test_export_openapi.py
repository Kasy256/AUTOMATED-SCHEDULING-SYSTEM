import json
from pathlib import Path

from cartlyf_api.export_openapi import main


def test_export_openapi_writes_schema_without_env(tmp_path: Path) -> None:
    out = tmp_path / "openapi.json"
    main([str(out)])
    schema = json.loads(out.read_text(encoding="utf-8"))
    assert schema["paths"]["/api/v1/health"]["get"]["operationId"] == "health"


def test_health_503_is_documented_as_problem_json(tmp_path: Path) -> None:
    out = tmp_path / "openapi.json"
    main([str(out)])
    schema = json.loads(out.read_text(encoding="utf-8"))
    content = schema["paths"]["/api/v1/health"]["get"]["responses"]["503"]["content"]
    problem = content["application/problem+json"]["schema"]
    assert set(problem["required"]) == {"title", "status"}
