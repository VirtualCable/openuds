import typing
import itertools
import collections.abc
import logging
import dataclasses
import datetime
import enum
import types as py_types

from uds.core import types, module
from uds.core.types.rest.api import SchemaProperty

if typing.TYPE_CHECKING:
    from uds.REST import model

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


def get_generic_types(
    cls: 'type[model.ModelHandler[typing.Any] | model.DetailHandler[typing.Any]]',
) -> list[type[types.rest.BaseRestItem]]:
    """
    Get the generic types of a model handler or detail handler class.

    Args:
        cls: The class to inspect. (Must be subclass of ModelHandler or DetailHandler)

    Note: Normally, for our models, will be or an empty list, or a list with just one element
        that is a subclass of BaseRestItem.
        Examples:
            class Test(ModelHandler[TheType]):
            ...
            if Test is resolvable and TheType is also resolvable, will return
            [TheType], else will return []
        We use the "list" version just in case, in a future, we have other kind of constructions
        with several elements.
    """
    base_types: list[type[types.rest.BaseRestItem]] = list(
        filter(
            lambda x: issubclass(x, types.rest.BaseRestItem),  # pyright: ignore[reportUnnecessaryIsInstance]
            itertools.chain.from_iterable(
                map(
                    lambda x: [
                        # Filter out non resolvable forward references of the ARGS, protect against failures
                        typing.cast(type[typing.Any], _resolve_forwardref(xx))
                        for xx in typing.get_args(x)
                        if _resolve_forwardref(xx) is not None
                    ],
                    [
                        # Filter out non resolvable forward references of the TYPE, protect against failures
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
    return base_types


def get_component_from_type(
    cls: 'type[model.ModelHandler[typing.Any] | model.DetailHandler[typing.Any]]',
) -> types.rest.api.Components:
    logger.debug('Getting components from type %s', cls)
    base_types = get_generic_types(cls)

    all_components = types.rest.api.Components()

    for base_type in base_types:
        logger.debug('Processing base %s for components %s', base_type, base_type.__bases__)
        components = base_type.api_components()

        # A reference
        item_name, item_schema = next(iter(components.schemas.items()))

        possible_types: collections.abc.Iterable[type['module.Module']] = []
        if issubclass(base_type, types.rest.ManagedObjectItem):
            # Managed object item class should provide types as it has "instance" field
            possible_types = cls.possible_types()
        else:  # BaseRestItem, does not have types as it does not have "instance" field
            pass

        refs: list[str] = []
        mappings: list[tuple[str, str]] = []
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
                type_schema.properties[field.name] = schema_property
                if field.gui.required is True:
                    type_schema.required.append(field.name)

            ref = f'#/components/schemas/{type_.type_type}'
            refs.append(ref)
            mappings.append((f'{type_.type_type}', ref))

            components.schemas[type_.type_type] = type_schema

        if issubclass(base_type, types.rest.ManagedObjectItem) and isinstance(
            item_schema, types.rest.api.Schema
        ):
            # item_schema.discriminator = types.rest.api.Discriminator(propertyName='type')
            instance_name = f'{item_name}Instance'
            item_schema.properties['instance'] = types.rest.api.SchemaProperty(
                type=f'#/components/schemas/{instance_name}'
            )
            instance_comps = types.rest.api.Components(
                schemas={instance_name: types.rest.api.RelatedSchema(property='type', mappings=mappings)}
            )
            all_components = all_components.union(instance_comps)

        # Store it
        all_components = all_components.union(components)

    return all_components


@dataclasses.dataclass(slots=True)
class OpenApiTypeInfo:
    type: str
    format: str | None = None
    ref: bool = False
    items: str | None = None  # Type of items in array

    def as_dict(self) -> dict[str, typing.Any]:
        dct: dict[str, typing.Any] = {'type': self.type}
        if self.format:
            dct['format'] = self.format
        if self.items:
            dct['items'] = {'type': self.items}
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
    LIST_STR = OpenApiTypeInfo(type='array', items='string')
    LIST_INT = OpenApiTypeInfo(type='array', items='integer')


_OPENAPI_TYPE_MAP: typing.Final[dict[typing.Any, OpenApiType]] = {
    int: OpenApiType.INTEGER,
    str: OpenApiType.STRING,
    float: OpenApiType.NUMBER,
    bool: OpenApiType.BOOLEAN,
    type(None): OpenApiType.NULL,
    datetime.datetime: OpenApiType.DATE_TIME,
    datetime.date: OpenApiType.DATE,
    list[str]: OpenApiType.LIST_STR,
    list[int]: OpenApiType.LIST_INT,
}


def python_type_to_openapi(py_type: typing.Any) -> 'types.rest.api.SchemaProperty':
    """
    Convert a Python type to an OpenAPI 3.1 schema property.
    """

    origin = typing.get_origin(py_type)
    args = typing.get_args(py_type)

    # list[...] → array
    if origin is list:
        item_type = args[0] if args else typing.Any
        return types.rest.api.SchemaProperty(type='array', items=python_type_to_openapi(item_type))

    # dict[...] → object
    elif origin is dict:
        value_type = args[1] if len(args) == 2 else typing.Any
        return types.rest.api.SchemaProperty(
            type='object', additionalProperties=python_type_to_openapi(value_type)
        )

    # Union[...] → oneOf
    # Except if one of them is None, in which case, we must extract it from the list
    # and create {'type': xxx, 'nullable': true}
    elif origin in {py_types.UnionType, typing.Union}:
        # Optional[X] is Union[X, None]
        # Note: the casting is because we use "is not", and cannot ad inner types
        one_of: list[SchemaProperty] = [
            python_type_to_openapi(arg)
            for arg in args
            if arg is not None
            and typing.get_origin(arg) is not typing.cast(typing.Any, collections.abc.Callable)
        ]
        # Remove repeated
        one_of = list({item.type: item for item in one_of}.values())
        # if only 1, return it directly
        if len(one_of) == 1:
            return one_of[0]

        return types.rest.api.SchemaProperty(
            type='not_used',
            one_of=one_of,
        )

    elif origin is typing.Annotated:
        return python_type_to_openapi(args[0])

    # Literal[...] → enum
    elif origin is typing.Literal:
        literal_type = typing.cast(type[typing.Any], type(args[0]) if args else str)
        return types.rest.api.SchemaProperty(
            type=_OPENAPI_TYPE_MAP.get(literal_type, OpenApiType.STRING).value.type, enum=list(args)
        )

    # Enum classes
    # First, IntEnum --> int
    elif isinstance(py_type, type) and issubclass(py_type, enum.IntEnum):
        return types.rest.api.SchemaProperty(type='integer', enum=[e.value for e in py_type])

    # Now, StrEnum --> string
    elif isinstance(py_type, type) and issubclass(py_type, enum.StrEnum):
        return types.rest.api.SchemaProperty(type='string', enum=[e.value for e in py_type])

    # Rest of cases --> enum with first item type setting the type for the field
    elif isinstance(py_type, type) and issubclass(py_type, enum.Enum):
        try:
            sample = next(iter(py_type))
            value_type = typing.cast(type[typing.Any], type(sample.value))
            openapi_type = _OPENAPI_TYPE_MAP.get(value_type, OpenApiType.STRING)
            return types.rest.api.SchemaProperty(type=openapi_type.value.type, enum=[e.value for e in py_type])
        except StopIteration:
            return types.rest.api.SchemaProperty(type='string')

    # Simple types
    oa_type = _OPENAPI_TYPE_MAP.get(py_type, OpenApiType.OBJECT)
    return types.rest.api.SchemaProperty(type=oa_type.value.type, format=oa_type.value.format)


def api_components(
    dataclass: typing.Type[typing.Any], *, removable_fields: list[str] | None = None
) -> 'types.rest.api.Components':
    from uds.core.util import api as api_util  # Avoid circular import

    # If not dataclass, raise a ValueError
    if not dataclasses.is_dataclass(dataclass):
        raise ValueError('Expected a dataclass')

    our_removables: set[str] = set()

    child_removables: dict[str, list[str]] = {}
    for rem_fld in removable_fields or []:
        if '.' in rem_fld:
            child_name, field = rem_fld.split('.', 1)
            if child_name not in child_removables:
                child_removables[child_name] = []

            child_removables[child_name].append(field)
        else:
            our_removables.add(rem_fld)

    components = types.rest.api.Components()
    schema = types.rest.api.Schema(type='object', properties={}, description=None)
    type_hints = typing.get_type_hints(dataclass)

    for field in dataclasses.fields(dataclass):
        if field.name in our_removables:
            continue

        # Check the type, can be a primitive or a complex type
        # complexes types accepted are list and dict currently
        field_type = type_hints.get(field.name)
        if not field_type:
            raise Exception(f'Field {field.name} has no type hint')

        # If it is a dataclass, get its API components
        if dataclasses.is_dataclass(field_type):
            sub_component = api_util.api_components(
                typing.cast(type[typing.Any], field_type),
                removable_fields=child_removables.get(field.name, []),
            )
            components = components.union(sub_component)
            schema_prop = types.rest.api.SchemaProperty(
                type=f'#/components/schemas/{next(iter(sub_component.schemas.keys()))}', description=None
            )
        else:
            schema_prop = api_util.python_type_to_openapi(field_type)

        schema.properties[field.name] = schema_prop
        if field.default is dataclasses.MISSING and field.default_factory is dataclasses.MISSING:
            schema.required.append(field.name)

    components.schemas[dataclass.__name__] = schema
    return components


def gen_response(
    type: str, with_404: bool = False, single: bool = True, delete: bool = False
) -> dict[str, types.rest.api.Response]:
    data: dict[str, types.rest.api.Response]

    if not single:
        data = {
            '200': types.rest.api.Response(
                description=f'Successfully retrieved all {type} items',
                content=types.rest.api.Content(
                    media_type='application/json',
                    schema=types.rest.api.SchemaProperty(
                        type='array',
                        items=types.rest.api.SchemaProperty(
                            type=f'#/components/schemas/{type}',
                        ),
                    ),
                ),
            )
        }
    else:
        data = {
            '200': types.rest.api.Response(
                description=f'Successfully {"retrieved" if not delete else "deleted"} {type} item',
                content=types.rest.api.Content(
                    media_type='application/json',
                    schema=types.rest.api.SchemaProperty(
                        type=f'#/components/schemas/{type}',
                    ),
                ),
            )
        }

    if with_404:
        data['404'] = types.rest.api.Response(
            description=f'{type} item not found',
            content=types.rest.api.Content(
                media_type='application/json',
                schema=types.rest.api.SchemaProperty(
                    type='object',
                    properties={
                        'detail': types.rest.api.SchemaProperty(
                            type='string',
                        )
                    },
                ),
            ),
        )

    return data
