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

from django.db.models import Q


logger = logging.getLogger(__name__)

from .query_filter import _QUERY_GRAMMAR, _FUNCTIONS_PARAMS_NUM

_DB_QUERY_PARSER_VAR: typing.Final[contextvars.ContextVar[lark.Lark]] = contextvars.ContextVar(
    "db_query_parser"
)

_REMOVE_QUOTES_RE: typing.Final[typing.Pattern[str]] = re.compile(r"^(['\"])(.*)\1$")


class DjangoQueryTransformer(lark.Transformer[typing.Any, Q]):
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
                case _:
                    raise ValueError(f"Unexpected token type: {arg.type}")
        return arg

    @lark.visitors.v_args(inline=True)
    def true(self) -> Q:
        return Q(pk__isnull=False)  # Always true

    @lark.visitors.v_args(inline=True)
    def false(self) -> Q:
        return ~Q(pk__isnull=False)  # Always false

    @lark.visitors.v_args(inline=True)
    def field(self, arg: lark.Token) -> str:
        return arg.value

    @lark.visitors.v_args(inline=True)
    def binary_expr(self, left: str, op: typing.Any, right: typing.Any) -> Q:
        match op:
            case 'eq':
                return Q(**{left: right})
            case 'ne':
                return ~Q(**{left: right})
            case 'gt':
                return Q(**{f"{left}__gt": right})
            case 'lt':
                return Q(**{f"{left}__lt": right})
            case 'ge':
                return Q(**{f"{left}__gte": right})
            case 'le':
                return Q(**{f"{left}__lte": right})
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
    def func_call(self, func: lark.Token, *args: typing.Any) -> Q:
        func_name = func.value.lower()
        if func_name not in _FUNCTIONS_PARAMS_NUM:
            raise ValueError(f"Unknown function: {func.value}")
        if len(args) != _FUNCTIONS_PARAMS_NUM[func_name]:
            raise ValueError(f"{func_name} requires {_FUNCTIONS_PARAMS_NUM[func_name]} arguments")

        field, value = args[0], args[1]

        if not isinstance(field, str):
            raise ValueError(f"Field name must be a string")

        match func_name:
            case 'substringof':
                return Q(**{f"{field}__icontains": value})
            case 'startswith':
                return Q(**{f"{field}__istartswith": value})
            case 'endswith':
                return Q(**{f"{field}__iendswith": value})
            case _:
                raise ValueError(f"Function {func_name} not supported in Django Q")


def get_parser() -> lark.Lark:
    """
    Returns the query parser instance, creating it if necessary.

    Returns:
        lark.Lark: The query parser.
    """
    try:
        return _DB_QUERY_PARSER_VAR.get()
    except LookupError:
        parser = lark.Lark(_QUERY_GRAMMAR, parser="lalr", transformer=DjangoQueryTransformer())
        _DB_QUERY_PARSER_VAR.set(parser)
        return parser


def exec_query(query: str) -> Q:
    """
    Parses a query string and returns a Django Q object.

    Args:
        query: The query string to parse.

    Returns:
        A Django Q object representing the parsed query.
    """
    try:
        return typing.cast(Q, get_parser().parse(query))
    except lark.exceptions.LarkError as e:
        logger.error(f"Error parsing query: {query}", exc_info=e)
        # Return empty queryset
        return Q(pk__isnull=True)  # Always false, as an empty queryset
