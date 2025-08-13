# Copyright (c) 2025 Virtual Cable S.L.U.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright notice,
#      this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright notice,
#      this list of conditions and the following disclaimer in the documentation
#      and/or other materials provided with the distribution.
#    * Neither the name of Virtual Cable S.L.U. nor the names of its contributors
#      may be used to endorse or promote products derived from this software
#      without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
# pyright: reportUnknownMemberType=false
import typing
import re
import contextvars
import logging

import lark

from django.db.models import Q, F, QuerySet
from django.db.models.functions import Lower, Upper, Length, ExtractYear, ExtractMonth, ExtractDay

logger = logging.getLogger(__name__)

from .query_filter import _QUERY_GRAMMAR, _FUNCTIONS_PARAMS_NUM

_DB_QUERY_PARSER_VAR: typing.Final[contextvars.ContextVar[lark.Lark]] = contextvars.ContextVar(
    "db_query_parser"
)

_REMOVE_QUOTES_RE: typing.Final[typing.Pattern[str]] = re.compile(r"^(['\"])(.*)\1$")


class FieldName(str):
    """Marker class to distinguish field names from string literals."""

    pass


class AnnotatedField(str):
    """Represents an annotated field name from a unary function."""

    pass


_UNARY_FUNCTIONS: typing.Final[dict[str, typing.Callable[[F], typing.Any]]] = {
    'tolower': Lower,
    'toupper': Upper,
    'length': Length,
    'year': ExtractYear,
    'month': ExtractMonth,
    'day': ExtractDay,
}


class DjangoQueryTransformer(lark.Transformer[typing.Any, Q]):
    def __init__(self):
        super().__init__()
        self.annotations: dict[str, typing.Any] = {}

    @lark.visitors.v_args(inline=True)
    def value(self, arg: lark.Token | str | int | float) -> typing.Any:
        if isinstance(arg, lark.Token):
            match arg.type:
                case 'ESCAPED_STRING':
                    match = _REMOVE_QUOTES_RE.match(arg.value)
                    return match.group(2) if match else arg.value
                case 'NUMBER':
                    return float(arg.value) if '.' in arg.value else int(arg.value)
                case 'BOOLEAN':
                    return arg.value.lower() == 'true'
                case 'CNAME':
                    return F(arg.value)
                case _:
                    raise ValueError(f"Unexpected token type: {arg.type}")
        return arg

    @lark.visitors.v_args(inline=True)
    def true(self) -> Q:
        return Q(pk__isnull=False)

    @lark.visitors.v_args(inline=True)
    def false(self) -> Q:
        return ~Q(pk__isnull=False)

    @lark.visitors.v_args(inline=True)
    def field(self, arg: lark.Token) -> FieldName:
        return FieldName(arg.value)

    @lark.visitors.v_args(inline=True)
    def binary_expr(self, left: typing.Any, op: typing.Any, right: typing.Any) -> Q:
        if isinstance(right, FieldName):
            right = F(right)

        if isinstance(left, AnnotatedField):
            field_name = str(left)
        elif isinstance(left, FieldName):
            field_name = str(left)
        elif isinstance(left, F):
            field_name = left.name
        else:
            raise ValueError(f"Left side of binary expression must be a field name or annotated field")

        match op:
            case 'eq':
                return Q(**{field_name: right})
            case 'ne':
                return ~Q(**{field_name: right})
            case 'gt':
                return Q(**{f"{field_name}__gt": right})
            case 'lt':
                return Q(**{f"{field_name}__lt": right})
            case 'ge':
                return Q(**{f"{field_name}__gte": right})
            case 'le':
                return Q(**{f"{field_name}__lte": right})
            case _:
                raise ValueError(f"Unknown operator: {op}")

    @lark.visitors.v_args(inline=True)
    def logical_and(self, left: Q, right: Q) -> Q:
        return left & right

    @lark.visitors.v_args(inline=True)
    def logical_or(self, left: Q, right: Q) -> Q:
        return left | right

    @lark.visitors.v_args(inline=True)
    def unary_not(self, expr: Q) -> Q:
        return ~expr

    @lark.visitors.v_args(inline=True)
    def paren_expr(self, expr: Q) -> Q:
        return expr

    @lark.visitors.v_args(inline=True)
    def func_call(self, func: lark.Token, *args: typing.Any) -> Q | AnnotatedField:
        func_name = func.value.lower()
        if func_name not in _FUNCTIONS_PARAMS_NUM:
            raise ValueError(f"Unknown function: {func.value}")
        if len(args) != _FUNCTIONS_PARAMS_NUM[func_name]:
            raise ValueError(f"{func_name} requires {_FUNCTIONS_PARAMS_NUM[func_name]} arguments")

        if func_name in ('substringof', 'startswith', 'endswith'):
            field, value = args[0], args[1]
            if not isinstance(field, str):
                raise ValueError(f"Field name must be a string")
            if isinstance(value, F):
                raise ValueError(f"Function '{func_name}' does not support field-to-field comparison")
            match func_name:
                case 'substringof':
                    return Q(**{f"{field}__icontains": value})
                case 'startswith':
                    return Q(**{f"{field}__istartswith": value})
                case 'endswith':
                    return Q(**{f"{field}__iendswith": value})

        if func_name in _UNARY_FUNCTIONS:
            field = args[0]
            if not isinstance(field, FieldName):
                raise ValueError(f"{func_name} requires a field name")
            alias = f"{func_name}_{field}"
            self.annotations[alias] = _UNARY_FUNCTIONS[func_name](F(field))
            return AnnotatedField(alias)

        raise ValueError(f"Function {func_name} not supported in Django Q")


def get_parser() -> lark.Lark:
    try:
        return _DB_QUERY_PARSER_VAR.get()
    except LookupError:
        transformer = DjangoQueryTransformer()
        parser = lark.Lark(_QUERY_GRAMMAR, parser="lalr", transformer=transformer)
        _DB_QUERY_PARSER_VAR.set(parser)
        return parser


T = typing.TypeVar('T', bound=typing.Any)


def exec_query(query: str, qs: QuerySet[T]) -> QuerySet[T]:
    try:
        transformer = DjangoQueryTransformer()
        parser = lark.Lark(_QUERY_GRAMMAR, parser="lalr", transformer=transformer)
        q_obj = typing.cast(Q, parser.parse(query))

        if transformer.annotations:
            qs = qs.annotate(**transformer.annotations)
            
        qs = qs.filter(q_obj)
        logger.debug(f"Executed query: {query} -> {q_obj}: {qs.query}")
        return qs

    except lark.exceptions.LarkError as e:
        logger.error(f"Error parsing query: {query}", exc_info=e)
        return qs.none()
