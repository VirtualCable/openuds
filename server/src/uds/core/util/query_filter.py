# Copyright (c) 2026 Virtual Cable S.L.U.
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
import collections.abc
import logging

import lark


logger = logging.getLogger(__name__)

_QUERY_GRAMMAR: typing.Final[
    str
] = r"""?start: expr

?expr: or_expr

?or_expr: and_expr
        | or_expr "or" and_expr   -> logical_or

?and_expr: not_expr
         | and_expr "and" not_expr -> logical_and

?not_expr: comparison
         | "not" not_expr          -> unary_not

?comparison: value
           | value OP value        -> binary_expr
           | "(" expr ")"          -> paren_expr

value: field | ESCAPED_STRING | NUMBER | boolean | func_call

field: NAME

func_call: NAME "(" [ value ("," value)* ] ")"

boolean: "true" -> true
       | "false" -> false

OP: "eq" | "gt" | "lt" | "ne" | "ge" | "le"
ESCAPED_STRING: /'[^']*'/ | /"[^"]*"/
NAME: CNAME ("." CNAME)*

%import common.CNAME
%import common.SIGNED_NUMBER -> NUMBER
%import common.WS
%ignore WS
"""
# with open("lark1.lark", "r") as f:
#     _QUERY_GRAMMAR = f.read()

# The idea is that parser returns a function that can be used to filter a list of dictionaries
# So we ensure all returned functions have the same signature and can be composed together
# Note that value can receive function or final values, as it is composed of
# terminals and
_T_Result: typing.TypeAlias = collections.abc.Callable[[dict[str, typing.Any]], typing.Any]

_QUERY_PARSER_VAR: typing.Final[contextvars.ContextVar[lark.Lark]] = contextvars.ContextVar("query_parser")

_REMOVE_QUOTES_RE: typing.Final[typing.Pattern[str]] = re.compile(r"^(['\"])(.*)\1$")

_FUNCTIONS_PARAMS_NUM: dict[str, int] = {
    'substringof': 2,
    'startswith': 2,
    'endswith': 2,
    'indexof': 2,
    'concat': 2,
    'tolower': 1,
    'toupper': 1,
    'length': 1,
    'year': 1,
    'month': 1,
    'day': 1,
}


# The transformer basic type is a lambda that will be evaluated "on the fly" after generating the parse tree
# This allows for dynamic filtering based on the parsed query.
class QueryTransformer(lark.Transformer[typing.Any, _T_Result]):
    @lark.visitors.v_args(inline=True)  # pyright: ignore
    def value(self, arg: lark.Token | str | int | float) -> _T_Result:
        value: typing.Any = arg
        if isinstance(arg, lark.Token):
            match arg.type:
                case 'ESCAPED_STRING':
                    match = _REMOVE_QUOTES_RE.match(arg.value)
                    if not match:
                        return arg.value
                    value = match.group(2)
                case 'NUMBER':
                    value = float(arg.value) if '.' in arg.value else int(arg.value)
                case 'BOOLEAN':
                    value = typing.cast(str, arg.value).lower() == 'true'
                case _:
                    raise ValueError(f"Unexpected token type: {arg.type}")
        elif isinstance(arg, typing.Callable):
            return lambda obj: typing.cast(_T_Result, arg)(obj)

        return lambda _obj: value

    @lark.visitors.v_args(inline=True)
    def true(self) -> _T_Result:
        return lambda obj: True

    @lark.visitors.v_args(inline=True)
    def false(self) -> _T_Result:
        return lambda obj: False

    @lark.visitors.v_args(inline=True)
    def field(self, arg: lark.Token) -> _T_Result:
        def getter(obj: dict[str, typing.Any]) -> typing.Any:
            for part in arg.value.split('.'):
                obj = obj.get(part, {})
            return obj

        return getter

    @lark.visitors.v_args(inline=True)
    def binary_expr(self, left: _T_Result, op: typing.Any, right: _T_Result) -> _T_Result:
        def _compare(left: str | int | float, right: str | int | float) -> int:
            if type(left) != type(right):
                # Convert both to string and compare
                left = str(left)
                right = str(right)
            #  0 -> are equal
            # <0 -> left is less than right
            # >0 -> left is greater than right
            if typing.cast(typing.Any, left) < typing.cast(typing.Any, right):
                return -1
            elif typing.cast(typing.Any, left) > typing.cast(typing.Any, right):
                return 1
            return 0

        match op:
            case "eq":
                return lambda item: _compare(left(item), right(item)) == 0
            case "gt":
                return lambda item: _compare(left(item), right(item)) > 0
            case "lt":
                return lambda item: _compare(left(item), right(item)) < 0
            case "ne":
                return lambda item: _compare(left(item), right(item)) != 0
            case "ge":
                return lambda item: _compare(left(item), right(item)) >= 0
            case "le":
                return lambda item: _compare(left(item), right(item)) <= 0
            case _:
                raise ValueError(f"Unknown operator: {op}")

    @lark.visitors.v_args(inline=True)
    def logical_and(self, left: _T_Result, right: _T_Result) -> _T_Result:
        return lambda item: left(item) and right(item)

    @lark.visitors.v_args(inline=True)
    def logical_or(self, left: _T_Result, right: _T_Result) -> _T_Result:
        return lambda item: left(item) or right(item)

    @lark.visitors.v_args(inline=True)
    def unary_not(self, expr: _T_Result) -> _T_Result:
        return lambda item: not expr(item)

    @lark.visitors.v_args(inline=True)
    def paren_expr(self, expr: _T_Result) -> _T_Result:
        return expr

    @lark.visitors.v_args(inline=True)
    def func_call(self, func: lark.Token, *args: _T_Result) -> _T_Result:
        func_name = func.value.lower()
        # If unknown function, raise an error
        if func_name not in _FUNCTIONS_PARAMS_NUM:
            raise ValueError(f"Unknown function: {func.value}")

        if len(args) != _FUNCTIONS_PARAMS_NUM[func_name]:
            raise ValueError(
                f"{func_name} function requires exactly {_FUNCTIONS_PARAMS_NUM[func_name]} arguments"
            )
        match func_name:
            case 'substringof':
                return lambda obj: str(args[1](obj)).find(str(args[0](obj))) != -1
            case 'startswith':
                return lambda obj: str(args[0](obj)).startswith(str(args[1](obj)))
            case 'endswith':
                return lambda obj: str(args[0](obj)).endswith(str(args[1](obj)))
            case 'indexof':
                return lambda obj: str(args[0](obj)).find(str(args[1](obj)))
            case 'concat':
                return lambda obj: str(args[0](obj)) + str(args[1](obj))
            case 'length':
                return lambda obj: len(str(args[0](obj)))
            case 'tolower':
                return lambda obj: str(args[0](obj)).lower()
            case 'toupper':
                return lambda obj: str(args[0](obj)).upper()
            case 'year':
                return lambda obj: str(args[0](obj)).split('-')[0] if isinstance(args[0](obj), str) else ''
            case 'month':
                return lambda obj: str(args[0](obj)).split('-')[1] if isinstance(args[0](obj), str) else ''
            case 'day':
                return lambda obj: str(args[0](obj)).split('-')[2] if isinstance(args[0](obj), str) else ''
            case _:
                # Will never reach this, as it has been already
                raise ValueError(f"Unknown function: {func.value}")


def get_parser() -> lark.Lark:
    try:
        return _QUERY_PARSER_VAR.get()
    except LookupError:
        parser = lark.Lark(_QUERY_GRAMMAR, parser="lalr", transformer=QueryTransformer())
        _QUERY_PARSER_VAR.set(parser)
        return parser


def exec_filter(data: list[dict[str, typing.Any]], query: str) -> typing.Iterable[dict[str, typing.Any]]:
    try:
        filter_func = typing.cast(_T_Result, get_parser().parse(query))
        return filter(filter_func, data)
    except Exception as e:
        raise ValueError(f"Error processing query: {e}") from None
