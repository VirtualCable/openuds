import typing
import dataclasses

from uds.core import exceptions

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


# Info general
@dataclasses.dataclass
class Info:
    title: str
    version: str
    description: str | None = None

    def as_dict(self) -> dict[str, typing.Any]:
        return {
            'title': self.title,
            'version': self.version,
            'description': self.description,
        }


# Parameter
@dataclasses.dataclass
class Parameter:
    name: str
    in_: str  # 'query', 'path', 'header', etc.
    required: bool
    schema: 'Schema'
    description: str | None = None
    style: str | None = None
    explode: bool | None = None

    def as_dict(self) -> dict[str, typing.Any]:
        return as_dict_without_none(
            {
                'name': self.name,
                'in': self.in_,
                'required': self.required,
                'schema': self.schema.as_dict(),
                'description': self.description,
                'style': self.style,
                'explode': self.explode,
            }
        )


@dataclasses.dataclass
class Content:
    media_type: str
    schema: 'SchemaProperty'

    def as_dict(self) -> dict[str, typing.Any]:
        return as_dict_without_none(
            {
                self.media_type: {
                    'schema': self.schema.as_dict(),
                },
            }
        )


# Request body
@dataclasses.dataclass
class RequestBody:
    required: bool
    content: Content  # e.g. {'application/json': {'schema': {...}}}

    def as_dict(self) -> dict[str, typing.Any]:
        return as_dict_without_none(
            {
                'required': self.required,
                'content': self.content.as_dict(),
            }
        )


# Response
@dataclasses.dataclass
class Response:
    description: str
    content: Content | None = None

    def as_dict(self) -> dict[str, typing.Any]:
        return as_dict_without_none(
            {
                'description': self.description,
                'content': self.content.as_dict() if self.content else None,
            }
        )


# Operación (GET, POST, etc.)
@dataclasses.dataclass
class Operation:

    summary: str | None = None
    description: str | None = None
    parameters: list[Parameter] = dataclasses.field(default_factory=list[Parameter])
    requestBody: RequestBody | None = None
    responses: dict[str, Response] = dataclasses.field(default_factory=dict[str, Response])
    security: str | None = None
    tags: list[str] = dataclasses.field(default_factory=list[str])

    def as_dict(self) -> dict[str, typing.Any]:
        data = as_dict_without_none(
            {
                'summary': self.summary,
                'description': self.description,
                'parameters': [param.as_dict() for param in self.parameters],
                'requestBody': self.requestBody.as_dict() if self.requestBody else None,
                'responses': {k: v.as_dict() for k, v in self.responses.items()},
                'tags': self.tags,
            }
        )
        if self.security:
            data['security'] = [{self.security: []}]
        return data


# Path item
@dataclasses.dataclass
class PathItem:
    get: Operation | None = None
    post: Operation | None = None
    put: Operation | None = None
    delete: Operation | None = None

    def as_dict(self) -> dict[str, typing.Any]:
        return as_dict_without_none(
            {
                'get': self.get.as_dict() if self.get else None,
                'post': self.post.as_dict() if self.post else None,
                'put': self.put.as_dict() if self.put else None,
                'delete': self.delete.as_dict() if self.delete else None,
            }
        )


# Schema property
@dataclasses.dataclass
class SchemaProperty:
    type: str | list[str]
    format: str | None = None  # e.g. 'date-time', 'int32', etc.
    description: str | None = None
    example: typing.Any | None = None
    items: 'SchemaProperty | None' = None  # For arrays
    additionalProperties: 'SchemaProperty | None' = None  # For objects
    discriminator: str | None = None  # For polymorphic types
    enum: list[str | int] | None = None  # For enum types
    properties: dict[str, 'SchemaProperty'] | None = None

    @staticmethod
    def from_field_desc(desc: 'ui.GuiElement') -> 'SchemaProperty|None':
        from uds.core.types import ui  # avoid circular import

        def base_schema() -> 'SchemaProperty|None':
            '''Returns the API type for this field type'''
            match desc.gui.type:
                case ui.FieldType.TEXT:
                    return SchemaProperty(type='string')
                case ui.FieldType.TEXT_AUTOCOMPLETE:
                    return SchemaProperty(type='string')
                case ui.FieldType.NUMERIC:
                    return SchemaProperty(type='number')
                case ui.FieldType.PASSWORD:
                    return SchemaProperty(type='string')
                case ui.FieldType.HIDDEN:
                    return None
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
                    return None
                case ui.FieldType.TAGLIST:
                    return SchemaProperty(type='array', items=SchemaProperty(type='string'))

        schema = base_schema()
        if schema is None:
            return None
        schema.description = f'{desc.gui.label}.{desc.gui.tooltip}'
        return schema

    def as_dict(self) -> dict[str, typing.Any]:
        val = {
            'type': self.type,
            'format': self.format,
            'description': self.description,
            'example': self.example,
            'items': self.items.as_dict() if self.items else None,
            'additionalProperties': self.additionalProperties.as_dict() if self.additionalProperties else None,
            'discriminator': self.discriminator,
            'enum': self.enum,
            'properties': {k: v.as_dict() for k, v in self.properties.items()} if self.properties else None,
        }

        # Convert type to oneOf if necesary, and add refs if needed
        def one_of_ref(type_: str) -> dict[str, typing.Any]:
            if type_.startswith('#'):
                return {'$ref': type_}
            return {'type': type_}

        if isinstance(self.type, list):
            # If one_of is defined, we should not use type, but one_of
            val['oneOf'] = [one_of_ref(ref) for ref in self.type]
            del val['type']
        elif self.type:
            del val['type']  # Remove existing type
            val.update(one_of_ref(self.type))
        return as_dict_without_none(val)


# Schema
@dataclasses.dataclass
class Schema:
    type: str
    format: str | None = None
    properties: dict[str, SchemaProperty] = dataclasses.field(default_factory=dict[str, SchemaProperty])
    required: list[str] = dataclasses.field(default_factory=list[str])
    description: str | None = None

    # For use on generating schemas

    def as_dict(self) -> dict[str, typing.Any]:
        return as_dict_without_none(
            {
                'type': self.type,
                'format': self.format,
                'properties': {k: v.as_dict() for k, v in self.properties.items()} if self.properties else None,
                'required': self.required if self.required else None,
                'description': self.description,
            }
        )


@dataclasses.dataclass
class RelatedSchema:
    property: str
    mappings: list[tuple[str, str]]  # list of (type, ref)

    def as_dict(self) -> dict[str, typing.Any]:
        return as_dict_without_none(
            {
                'oneOf': [{'$ref': i[1]} for i in self.mappings],
                'discriminator': {
                    'propertyName': self.property,
                    'mapping': {i[0]: i[1] for i in self.mappings},
                },
            }
        )


# Componentes
@dataclasses.dataclass
class Components:
    schemas: dict[str, Schema | RelatedSchema] = dataclasses.field(
        default_factory=dict[str, Schema | RelatedSchema]
    )
    securitySchemes: dict[str, typing.Any] = dataclasses.field(default_factory=dict[str, typing.Any])

    def as_dict(self) -> dict[str, typing.Any]:
        return as_dict_without_none(
            {
                'schemas': {k: v.as_dict() for k, v in self.schemas.items()},
                'securitySchemes': self.securitySchemes if self.securitySchemes else None,
            }
        )

    def union(self, other: 'Components') -> 'Components':
        '''Returns a new Components instance that is the union of this and another Components.'''
        new_components = Components()
        new_components.schemas = {**self.schemas, **other.schemas}
        if other.securitySchemes:
            new_components.securitySchemes = {**self.securitySchemes, **other.securitySchemes}
        return new_components

    # Operator | will union two Components
    def __or__(self, other: 'Components') -> 'Components':
        return self.union(other)

    def is_empty(self) -> bool:
        return not self.schemas


# Documento OpenAPI completo
@dataclasses.dataclass
class OpenAPI:
    @staticmethod
    def _get_system_version() -> Info:
        from uds.core.consts import system

        return Info(title='UDS API', version=system.VERSION, description='UDS REST API Documentation')

    openapi: str = '3.1.0'
    info: Info = dataclasses.field(default_factory=lambda: OpenAPI._get_system_version())
    paths: dict[str, PathItem] = dataclasses.field(default_factory=dict[str, PathItem])
    components: Components = dataclasses.field(default_factory=Components)

    def as_dict(self) -> dict[str, typing.Any]:
        return as_dict_without_none(
            {
                'openapi': self.openapi,
                'info': self.info.as_dict(),
                'paths': {k: v.as_dict() for k, v in self.paths.items()},
                'components': self.components.as_dict(),
            }
        )


@dataclasses.dataclass
class ODataParams:
    """
    OData query parameters converter
    """

    filter: str | None = None  # $filter=....
    start: int | None = None  # $skip=... zero based
    limit: int | None = None  # $top=... defaults to unlimited right now
    orderby: list[str] = dataclasses.field(default_factory=list[str])  # $orderby=xxx, yyy asc, zzz desc
    select: set[str] = dataclasses.field(default_factory=set[str])  # $select=...

    @staticmethod
    def from_dict(data: dict[str, typing.Any]) -> 'ODataParams':
        try:
            # extract order by, split by ',' and replace asc by '' and desc by a '-' stripping text.
            # After this, move the - to the beginning when needed
            order_fld = typing.cast(str, data.get('$orderby', ''))
            order_by = list(
                map(
                    lambda x: f'-{x.rstrip("-")}' if x.endswith('-') else x,
                    [
                        item.strip().replace(' asc', '').replace(' desc', '-')
                        for item in order_fld.split(',')
                        if item
                    ],
                )
            )
            select_fld = typing.cast(str, data.get('$select', ''))
            select = {item.strip() for item in select_fld.split(',') if item}
            start = int(data.get('$skip', 0)) if data.get('$skip') is not None else None
            limit = int(data.get('$top', 0)) if data.get('$top') is not None else None
            return ODataParams(
                filter=data.get('$filter'),
                start=start,
                limit=limit,
                orderby=order_by,
                select=select,
            )
        except (ValueError, TypeError):
            raise exceptions.rest.RequestError('Invalid OData query parameters')

    def select_filter(self, d: dict[str, typing.Any]) -> dict[str, typing.Any]:
        """
        Filters a dictionary by the OData parameters.

        Args:
            d: The dictionary to filter.

        Returns:
            A new dictionary containing only the keys from the original dictionary that are in the OData select set.

        Note:
            If the OData select set is empty, all keys are kept.
        """
        if not self.select:
            return d

        return {k: v for k, v in d.items() if k in self.select}
