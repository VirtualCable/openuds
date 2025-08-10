import typing
import itertools
import collections.abc
import logging

from uds.core import types, module

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
    # item_type_hint = typing.get_type_hints(cls.get_item).get('return')
    if item_type_hint is None or not issubclass(item_type_hint, types.rest.BaseRestItem):
        raise Exception(
            f'get_item method of {cls.__name__} must have a return type hint subclass of types.rest.BaseRestItem'
        )

    components = item_type_hint.api_components()
    # Components has only 1 schema, which is the item schema
    item_schema = next(iter(components.schemas.values()))

    refs: list[str] = []
    # # Component schemas
    # for type_ in cls.enum_types():
    #     schema = types.rest.api.Schema(
    #         type='object',
    #         required=[],
    #         description=type_.__doc__ or None,
    #     )
    #     for field in type_.describe_fields():
    #         schema_property = types.rest.api.SchemaProperty.from_field_desc(field)
    #         if schema_property is None:
    #             continue  # Skip fields that don't have a schema property
    #         schema.properties[field['name']] = schema_property
    #         if field['gui'].get('required', False):
    #             schema.required.append(field['name'])

    #     refs.append(f'#/components/schemas/{type_.type_type}')

    #     components.schemas[type_.type_type] = schema

    # The item is
    if issubclass(item_type_hint, types.rest.ManagedObjectItem):
        item_schema.properties['instance'] = types.rest.api.SchemaProperty(type=refs, discriminator='type')

    return components
