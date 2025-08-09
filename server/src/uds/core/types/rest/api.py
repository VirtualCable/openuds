import types as python_types
import typing
import enum
import dataclasses

if typing.TYPE_CHECKING:
    from uds.core.types import ui


def as_dict_without_none(v: typing.Any) -> typing.Any:
    if hasattr(v, 'as_dict'):
        return as_dict_without_none(v.as_dict())
    elif dataclasses.is_dataclass(v):
        return as_dict_without_none(dataclasses.asdict(typing.cast(typing.Any, v)))
    elif isinstance(v, list):
        return [as_dict_without_none(item) for item in typing.cast(list[typing.Any], v) if item is not None]
    elif isinstance(v, dict):
        return {
            k: as_dict_without_none(val)
            for k, val in typing.cast(dict[str, typing.Any], v).items()
            if val is not None
        }
    elif hasattr(v, 'as_dict'):
        return v.as_dict()
    return v


_OPENAPI_TYPE_MAP: typing.Final[dict[typing.Any, str]] = {
    int: 'integer',
    str: 'string',
    float: 'number',
    bool: 'boolean',
    type(None): 'null',
}


def python_type_to_openapi(py_type: typing.Any) -> 'SchemaProperty':
    """
    Convert a Python type to an OpenAPI 3.1 schema property.
    """
    origin = typing.get_origin(py_type)
    args = typing.get_args(py_type)

    # list[...] → array
    if origin is list:
        item_type = args[0] if args else typing.Any
        return SchemaProperty(type='array', items=python_type_to_openapi(item_type))

    # dict[...] → object
    elif origin is dict:
        value_type = args[1] if len(args) == 2 else typing.Any
        return SchemaProperty(type='object', additionalProperties=python_type_to_openapi(value_type))

    # Union[...] → oneOf
    elif origin in {python_types.UnionType, typing.Union}:
        # Optional[X] is Union[X, None]
        return SchemaProperty(
            type=[_OPENAPI_TYPE_MAP.get(arg, 'object') for arg in args if isinstance(arg, type)],
        )

    elif origin is typing.Annotated:
        return python_type_to_openapi(args[0])

    # Literal[...] → enum
    elif origin is typing.Literal:
        literal_type = typing.cast(type[typing.Any], type(args[0]) if args else str)
        return SchemaProperty(type=_OPENAPI_TYPE_MAP.get(literal_type, 'string'), enum=list(args))

    # Enum classes
    elif isinstance(py_type, type) and issubclass(py_type, enum.Enum):
        try:
            sample = next(iter(py_type))
            value_type = typing.cast(type[typing.Any], type(sample.value))
            openapi_type = _OPENAPI_TYPE_MAP.get(value_type, 'string')
            return SchemaProperty(type=openapi_type, enum=[e.value for e in py_type])
        except StopIteration:
            return SchemaProperty(type='string')

    # Simple types
    return SchemaProperty(type=_OPENAPI_TYPE_MAP.get(py_type, 'object'))


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
    type: str | list[str]
    description: str | None = None
    example: typing.Any | None = None
    items: 'SchemaProperty | None' = None  # For arrays
    additionalProperties: 'SchemaProperty | None' = None  # For objects
    discriminator: str | None = None  # For polymorphic types
    enum: list[str | int] | None = None  # For enum types

    @staticmethod
    def from_field_desc(desc: 'ui.GuiElement') -> 'SchemaProperty':
        from uds.core.types import ui  # avoid circular import

        def base_schema() -> 'SchemaProperty':
            '''Returns the API type for this field type'''
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
        val = as_dict_without_none(dataclasses.asdict(self))

        # Convert type to oneOf if necesary, and add refs if needed
        def one_of_ref(type_: str) -> dict[str, typing.Any]:
            if type_.startswith('#'):
                return {'$ref': type_}
            return {'type': type_}

        if isinstance(self.type, list):
            # If one_of is defined, we should not use type, but one_of
            val['oneOf'] = [one_of_ref(ref) for ref in self.type]
            del val['type']
        return as_dict_without_none(val)


# Schema
@dataclasses.dataclass
class Schema:
    type: str
    properties: dict[str, SchemaProperty] = dataclasses.field(default_factory=dict[str, SchemaProperty])
    required: list[str] = dataclasses.field(default_factory=list[str])
    description: str | None = None

    # For use on generating schemas

    def as_dict(self) -> dict[str, typing.Any]:
        return as_dict_without_none(
            {
                'type': self.type,
                'properties': {k: v.as_dict() for k, v in self.properties.items()},
                'required': self.required,
                'description': self.description,
            }
        )


# Componentes
@dataclasses.dataclass
class Components:
    schemas: dict[str, Schema] = dataclasses.field(default_factory=dict[str, Schema])

    def as_dict(self) -> dict[str, typing.Any]:
        return as_dict_without_none(
            {
                'schemas': {k: v.as_dict() for k, v in self.schemas.items()},
            }
        )

    def union(self, other: 'Components') -> 'Components':
        '''Returns a new Components instance that is the union of this and another Components.'''
        new_components = Components()
        new_components.schemas = {**self.schemas, **other.schemas}
        return new_components


# Documento OpenAPI completo
@dataclasses.dataclass
class OpenAPI:
    @staticmethod
    def _get_system_version() -> Info:
        from uds.core.consts import system

        return Info(title='UDS API', version=system.VERSION)

    openapi: str = '3.1.0'
    info: Info = dataclasses.field(default_factory=lambda: OpenAPI._get_system_version())
    paths: dict[str, PathItem] = dataclasses.field(default_factory=dict[str, PathItem])
    components: Components = dataclasses.field(default_factory=Components)
