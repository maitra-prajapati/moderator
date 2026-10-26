import httpx

from backend.contracts.validate_v_1 import validate_json, print_validation_result

response = httpx.get(
    "http://127.0.0.1:8000/api/v1/brands/brand_flowpilot/knowledge"
)

result = validate_json(
    response.json(),
    "knowledge-snapshot"
)

print_validation_result(result)