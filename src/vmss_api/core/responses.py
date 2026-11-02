import math
from typing import Any

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import ValidationError


def success_response(
    data: Any = None,
    message: str = "Success",
    status_code: int = 200,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": True, "message": message, "data": jsonable_encoder(data)},
    )


def paginated_response(
    data: Any,
    *,
    page: int,
    page_size: int,
    total: int,
    message: str = "Success",
    status_code: int = 200,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": True,
            "message": message,
            "data": jsonable_encoder(data),
            "pagination": {
                "page": page,
                "pageSize": page_size,
                "total": total,
                "totalPages": math.ceil(total / page_size) if page_size else 0,
            },
        },
    )


def error_response(
    message: str = "Error",
    status_code: int = 400,
    errors: Any = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "message": message, "errors": jsonable_encoder(errors)},
    )


def mark_deprecated(response: JSONResponse) -> JSONResponse:
    """Marks a response as coming from a deprecated route (api-conventions.md
    §2), via the standard `Deprecation` response header (RFC 8594), so a
    client library can surface the signal without parsing the docs note."""
    response.headers["Deprecation"] = "true"
    return response


def validation_error_response(exc: ValidationError) -> JSONResponse:
    """422 for a payload that failed model validation, naming each failing
    field and why — without `str(exc)`'s echo of the submitted input values
    (which can carry PII) or its pydantic docs URL."""
    problems = []
    for error in exc.errors(include_url=False, include_input=False):
        location = ".".join(str(part) for part in error["loc"]) or "payload"
        message = str(error["msg"]).removeprefix("Value error, ")
        problems.append({"field": location, "message": message})
    summary = "; ".join(
        p["message"] if p["field"] == "payload" else f"{p['field']}: {p['message']}"
        for p in problems
    )
    return error_response(
        message=f"Invalid request: {summary}" if summary else "Invalid request",
        status_code=422,
        errors=problems,
    )
