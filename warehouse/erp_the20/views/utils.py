# views/utils.py
"""
Shared tooling for drf-spectacular docs on APIView classes.
Usage in your views:
    from .utils import (
        extend_schema, extend_schema_view,
        OpenApiParameter, OpenApiExample, OpenApiResponse,
        OpenApiTypes, inline_serializer,
        ErrorSerializer, path_int, q_int, q_str, q_date, q_datetime,
        responses_ok, std_errors,
    )
"""
from drf_spectacular.utils import (
    extend_schema, extend_schema_view,
    OpenApiParameter, OpenApiExample, OpenApiResponse, inline_serializer,
)
from drf_spectacular.types import OpenApiTypes
from rest_framework import serializers

# ---- Reusable error schema
ErrorSerializer = inline_serializer(
    name="Error",
    fields={"detail": serializers.CharField()}
)

# ---- Param helpers

def path_int(name: str, description: str):
    return OpenApiParameter(name, OpenApiTypes.INT, OpenApiParameter.PATH, description=description)

def q_int(name: str, description: str, required: bool = False):
    return OpenApiParameter(name, OpenApiTypes.INT, OpenApiParameter.QUERY, required=required, description=description)

def q_str(name: str, description: str, required: bool = False):
    return OpenApiParameter(name, OpenApiTypes.STR, OpenApiParameter.QUERY, required=required, description=description)

def q_date(name: str, description: str, required: bool = False):
    return OpenApiParameter(name, OpenApiTypes.DATE, OpenApiParameter.QUERY, required=required, description=description)

def q_datetime(name: str, description: str, required: bool = False):
    return OpenApiParameter(name, OpenApiTypes.DATETIME, OpenApiParameter.QUERY, required=required, description=description)

# ---- Convenience for common responses

def responses_ok(serializer_cls, many: bool = False, description: str | None = None, extra: dict | None = None):
    """Build a {200: ...} response mapping quickly."""
    serializer = serializer_cls(many=many) if isinstance(serializer_cls, type) else serializer_cls
    mapping = {200: OpenApiResponse(response=serializer, description=description or "OK")}
    if extra:
        mapping.update(extra)
    return mapping


def std_errors(extra: dict | None = None):
    """Standard error response mapping you can merge into responses=..."""
    errs = {
        400: OpenApiResponse(ErrorSerializer, description="Bad Request"),
        401: OpenApiResponse(ErrorSerializer, description="Unauthorized"),
        403: OpenApiResponse(ErrorSerializer, description="Forbidden"),
        404: OpenApiResponse(ErrorSerializer, description="Not Found"),
    }
    if extra:
        errs.update(extra)
    return errs