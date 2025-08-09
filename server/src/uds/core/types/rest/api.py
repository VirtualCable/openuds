import typing
import dataclasses

if typing.TYPE_CHECKING:
    from uds.core.types import ui


def as_dict_without_none(v: typing.Any) -> typing.Any:
    if dataclasses.is_dataclass(v):
        return as_dict_without_none(dataclasses.asdict(typing.cast(typing.Any, v)))
    elif isinstance(v, list):
        return [as_dict_without_none(item) for item in typing.cast(list[typing.Any], v) if item is not None]
    elif isinstance(v, dict):
        return {k: as_dict_without_none(val) for k, val in typing.cast(dict[str, typing.Any], v).items() if val is not None}
    elif hasattr(v, 'as_dict'):
        return v.as_dict()
    return v


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


# Schema property
@dataclasses.dataclass
class SchemaProperty:
    type: str
    description: str | None = None
    example: typing.Any | None = None
    items: 'SchemaProperty | None' = None  # For arrays

    @staticmethod
    def from_field_desc(desc: 'ui.GuiElement') -> 'SchemaProperty':
        from uds.core.types import ui  # avoid circular import

        def base_schema() -> 'SchemaProperty':
            """Returns the API type for this field type"""
            match desc['gui']['type']:
                case ui.FieldType.TEXT:
                    return SchemaProperty(type='string')
                case ui.FieldType.TEXT_AUTOCOMPLETE:
                    return SchemaProperty(type='string')
                case ui.FieldType.NUMERIC:
                    return SchemaProperty(type='number')
                case ui.FieldType.PASSWORD:
                    return SchemaProperty(type='string')
                case ui.FieldType.HIDDEN:
                    return SchemaProperty(type='string')
                case ui.FieldType.CHOICE:
                    return SchemaProperty(type='string')
                case ui.FieldType.MULTICHOICE:
                    return SchemaProperty(type='array', items=SchemaProperty(type='string'))
                case ui.FieldType.EDITABLELIST:
                    return SchemaProperty(type='array', items=SchemaProperty(type='string'))
                case ui.FieldType.CHECKBOX:
                    return SchemaProperty(type='boolean')
                case ui.FieldType.IMAGECHOICE:
                    return SchemaProperty(type='string')
                case ui.FieldType.DATE:
                    return SchemaProperty(type='string')
                case ui.FieldType.INFO:
                    return SchemaProperty(type='string')
                case ui.FieldType.TAGLIST:
                    return SchemaProperty(type='array', items=SchemaProperty(type='string'))
        schema = base_schema()
        schema.description = f'{desc['gui']['label']}.{desc['gui'].get('tooltip', '')}'
        return schema

    def as_dict(self) -> dict[str, typing.Any]:
        return as_dict_without_none(self)


# Schema
@dataclasses.dataclass
class Schema:
    type: str
    properties: dict[str, SchemaProperty] = dataclasses.field(default_factory=dict[str, SchemaProperty])
    required: list[str] = dataclasses.field(default_factory=list[str])
    description: str | None = None
    additionalProperties: bool | dict[str, typing.Any] | None = None

    # For use on generating schemas

    def as_dict(self) -> dict[str, typing.Any]:
        return as_dict_without_none(self)


# Componentes
@dataclasses.dataclass
class Components:
    schemas: dict[str, Schema] = dataclasses.field(default_factory=dict[str, Schema])

    def as_dict(self) -> dict[str, typing.Any]:
        return as_dict_without_none(self)


# Documento OpenAPI completo
@dataclasses.dataclass
class OpenAPI:
    @staticmethod
    def _get_system_version() -> Info:
        from uds.core.consts import system

        return Info(title="UDS API", version=system.VERSION)

    openapi: str = "3.0.0"
    info: Info = dataclasses.field(default_factory=lambda: OpenAPI._get_system_version())
    paths: dict[str, PathItem] = dataclasses.field(default_factory=dict[str, PathItem])
    components: Components = dataclasses.field(default_factory=Components)
