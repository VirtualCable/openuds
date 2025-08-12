import typing
import itertools
import collections.abc
import logging
import dataclasses
import datetime
import enum
import types as py_types

from uds.core import types, module

if typing.TYPE_CHECKING:
    from uds.REST import model
    from uds.core.types.rest import api

logger = logging.getLogger(__name__)


def _resolve_forwardref(
    ref: typing.Any, globalns: dict[str, typing.Any] | None = None, localns: dict[str, typing.Any] | None = None
):
    if isinstance(ref, typing.ForwardRef):
        # if not already evaluated, raise an exception
        if not ref.__forward_evaluated__:
            return None
        return ref.__forward_value__
    return ref


def get_component_from_type(
    cls: 'type[model.ModelHandler[typing.Any] | model.DetailHandler[typing.Any]]',
) -> types.rest.api.Components:
    logger.debug('Getting components from type %s', cls)
    base_types: list[type[types.rest.BaseRestItem]] = list(
        filter(
            lambda x: issubclass(x, types.rest.BaseRestItem),  # pyright: ignore[reportUnnecessaryIsInstance]
            itertools.chain.from_iterable(
                map(
                    lambda x: [
                        # Filter out non resolvable forward references, protect against failures
                        typing.cast(type[typing.Any], _resolve_forwardref(xx))
                        for xx in typing.get_args(x)
                        if _resolve_forwardref(xx) is not None
                    ],
                    [
                        # Filter out non resolvable forward references, protect against failures
                        typing.cast(type[typing.Any], _resolve_forwardref(base))
                        for base in filter(
                            lambda x: _resolve_forwardref(x) is not None,
                            [base for base in getattr(cls, '__orig_bases__', [])],
                        )
                    ],
                )
            ),
        )
    )

    all_components = types.rest.api.Components()

    for base_type in base_types:
        logger.debug('Processing base %s for components %s', base_type, base_type.__bases__)
        components = base_type.api_components()

        item_schema = next(iter(components.schemas.values()))

        possible_types: collections.abc.Iterable[type['module.Module']] = []
        if issubclass(base_type, types.rest.ManagedObjectItem):
            # Managed object item class should provide types as it has "instance" field
            possible_types = cls.possible_types()
        else:  # BaseRestItem, does not have types as it does not have "instance" field
            pass

        refs: list[str] = []
        for type_ in possible_types:
            type_schema = types.rest.api.Schema(
                type='object',
                required=[],
                description=type_.__doc__ or None,
            )
            for field in type_.describe_fields():
                schema_property = types.rest.api.SchemaProperty.from_field_desc(field)
                if schema_property is None:
                    continue  # Skip fields that don't have a schema property
                type_schema.properties[field['name']] = schema_property
                if field['gui'].get('required', False):
                    type_schema.required.append(field['name'])

            refs.append(f'#/components/schemas/{type_.type_type}')

            components.schemas[type_.type_type] = type_schema

        if issubclass(base_type, types.rest.ManagedObjectItem):
            item_schema.properties['instance'] = types.rest.api.SchemaProperty(type=refs, discriminator='type')

        # Store it
        all_components = all_components.union(components)

    return all_components


@dataclasses.dataclass(slots=True)
class OpenApiTypeInfo:
    type: str
    format: str | None = None

    def as_dict(self) -> dict[str, typing.Any]:
        dct = {'type': self.type}
        if self.format:
            dct['format'] = self.format
        return dct


class OpenApiType(enum.Enum):
    OBJECT = OpenApiTypeInfo(type='object')
    INTEGER = OpenApiTypeInfo(type='integer', format='int64')
    STRING = OpenApiTypeInfo(type='string')
    NUMBER = OpenApiTypeInfo(type='number')
    BOOLEAN = OpenApiTypeInfo(type='boolean')
    NULL = OpenApiTypeInfo(type='null')
    DATE_TIME = OpenApiTypeInfo(type='string', format='date-time')
    DATE = OpenApiTypeInfo(type='string', format='date')


_OPENAPI_TYPE_MAP: typing.Final[dict[typing.Any, OpenApiType]] = {
    int: OpenApiType.INTEGER,
    str: OpenApiType.STRING,
    float: OpenApiType.NUMBER,
    bool: OpenApiType.BOOLEAN,
    type(None): OpenApiType.NULL,
    datetime.datetime: OpenApiType.DATE_TIME,
    datetime.date: OpenApiType.DATE,
}


def python_type_to_openapi(py_type: typing.Any) -> 'api.SchemaProperty':
    """
    Convert a Python type to an OpenAPI 3.1 schema property.
    """
    from uds.core.types.rest import api

    origin = typing.get_origin(py_type)
    args = typing.get_args(py_type)

    # list[...] → array
    if origin is list:
        item_type = args[0] if args else typing.Any
        return api.SchemaProperty(type='array', items=python_type_to_openapi(item_type))

    # dict[...] → object
    elif origin is dict:
        value_type = args[1] if len(args) == 2 else typing.Any
        return api.SchemaProperty(type='object', additionalProperties=python_type_to_openapi(value_type))

    # Union[...] → oneOf
    elif origin in {py_types.UnionType, typing.Union}:
        # Optional[X] is Union[X, None]
        oa_types = [_OPENAPI_TYPE_MAP.get(arg, OpenApiType.OBJECT) for arg in args if isinstance(arg, type)]
        return api.SchemaProperty(
            type=[oa_type.value.type for oa_type in oa_types],
        )

    elif origin is typing.Annotated:
        return python_type_to_openapi(args[0])

    # Literal[...] → enum
    elif origin is typing.Literal:
        literal_type = typing.cast(type[typing.Any], type(args[0]) if args else str)
        return api.SchemaProperty(
            type=_OPENAPI_TYPE_MAP.get(literal_type, OpenApiType.STRING).value.type, enum=list(args)
        )

    # Enum classes
    # First, IntEnum --> int
    elif isinstance(py_type, type) and issubclass(py_type, enum.IntEnum):
        return api.SchemaProperty(type='integer')

    # Now, StrEnum --> string
    elif isinstance(py_type, type) and issubclass(py_type, enum.StrEnum):
        return api.SchemaProperty(type='string')

    # Rest of cases --> enum with first item type setting the type for the field
    elif isinstance(py_type, type) and issubclass(py_type, enum.Enum):
        try:
            sample = next(iter(py_type))
            value_type = typing.cast(type[typing.Any], type(sample.value))
            openapi_type = _OPENAPI_TYPE_MAP.get(value_type, OpenApiType.STRING)
            return api.SchemaProperty(type=openapi_type.value.type, enum=[e.value for e in py_type])
        except StopIteration:
            return api.SchemaProperty(type='string')

    # Simple types
    oa_type = _OPENAPI_TYPE_MAP.get(py_type, OpenApiType.OBJECT)
    return api.SchemaProperty(type=oa_type.value.type, format=oa_type.value.format)


def api_components(dataclass: typing.Type[typing.Any]) -> 'api.Components':
    from uds.core.util import api as api_uti  # Avoid circular import
    from uds.core.types.rest import api

    # If not dataclass, raise a ValueError
    if not dataclasses.is_dataclass(dataclass):
        raise ValueError('Expected a dataclass')

    components = api.Components()
    schema = api.Schema(type='object', properties={}, description=None)
    type_hints = typing.get_type_hints(dataclass)

    for field in dataclasses.fields(dataclass):
        # Check the type, can be a primitive or a complex type
        # complexes types accepted are list and dict currently
        field_type = type_hints.get(field.name)
        if not field_type:
            raise Exception(f'Field {field.name} has no type hint')

        # If it is a dataclass, get its API components
        if dataclasses.is_dataclass(field_type):
            sub_component = api_uti.api_components(typing.cast(type[typing.Any], field_type))
            components = components.union(sub_component)
            schema_prop = api.SchemaProperty(type=next(iter(sub_component.schemas.keys())), description=None)
        else:
            schema_prop = api_uti.python_type_to_openapi(field_type)

        schema.properties[field.name] = schema_prop
        if field.default is dataclasses.MISSING and field.default_factory is dataclasses.MISSING:
            schema.required.append(field.name)

    components.schemas[dataclass.__name__] = schema
    return components
