# example of submission-create schema check while setting up fastapi server

from docs.contracts.validate_v_1 import validate_json, print_validation_result
from fastapi import FastAPI, HTTPException, Request


app = FastAPI()

@app.post("/api/v1/submissions")
async def create_submission(request : Request):
    data = await request.json()

    result = validate_json(data, "submission-create")

    print_validation_result(result)

    if not result["valid"]:
        raise HTTPException(
            status_code=422,
            detail=result["errors"]
        )

    return {
        "message" : "input validated successfully",
        'data' : data
    }
