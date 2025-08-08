import typing
import dataclasses

from uds.core import consts


# Info general
@dataclasses.dataclass
class Info:
    title: str
    version: str
    description: str | None = None


# Parámetro
@dataclasses.dataclass
class Parameter:
    name: str
    in_: str  # 'query', 'path', 'header', etc.
    required: bool
    schema: dict[str, typing.Any]
    description: str | None = None


# Request body
@dataclasses.dataclass
class RequestBody:
    required: bool
    content: dict[str, typing.Any]  # e.g. {'application/json': {'schema': {...}}}


# Response
@dataclasses.dataclass
class Response:
    description: str
    content: dict[str, typing.Any] | None = None


# Operación (GET, POST, etc.)
@dataclasses.dataclass
class Operation:
    summary: str | None = None
    description: str | None = None
    parameters: list[Parameter] = dataclasses.field(default_factory=list[Parameter])
    requestBody: RequestBody | None = None
    responses: dict[str, Response] = dataclasses.field(default_factory=dict[str, Response])
    tags: list[str] = dataclasses.field(default_factory=list[str])


# Path item
@dataclasses.dataclass
class PathItem:
    get: Operation | None = None
    post: Operation | None = None
    put: Operation | None = None
    delete: Operation | None = None


# Schema
@dataclasses.dataclass
class Schema:
    type: str
    properties: dict[str, typing.Any] | None = None
    required: list[str] | None = None
    description: str | None = None
    additionalProperties: bool | dict[str, typing.Any] | None = None


# Componentes
@dataclasses.dataclass
class Components:
    schemas: dict[str, Schema] = dataclasses.field(default_factory=dict[str, Schema])


# Documento OpenAPI completo
@dataclasses.dataclass
class OpenAPI:
    openapi: str = "3.0.0"
    info: Info = dataclasses.field(default_factory=lambda: Info(title="UDS API", version=consts.system.VERSION))
    paths: dict[str, PathItem] = dataclasses.field(default_factory=dict[str, PathItem])
    components: Components = dataclasses.field(default_factory=Components)
