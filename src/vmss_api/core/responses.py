import math
from typing import Any

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse


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
