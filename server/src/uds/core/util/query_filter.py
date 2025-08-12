import typing
import collections.abc
import contextvars


from lark import Lark, Transformer, Token

# Simplified Odata grammar
_ODATA_GRAMMAR: typing.Final[
    str
] = r"""
?start: expr

?expr: "not" expr        -> not_expr
     | expr "and" expr   -> and_expr
     | expr "or" expr    -> or_expr
     | "(" expr ")"      -> paren_expr
     | comparison

?func_name: CNAME

OP: "eq" | "gt" | "lt" | "ne" | "ge" | "le"

?comparison: operand OP operand       -> binary_op
           | func_name "(" field "," value ")" -> func_op

?operand: value_expr
        | value

?value_expr: field
           | func_name "(" field ")"   -> value_func

field: CNAME
value: ESCAPED_STRING | SIGNED_NUMBER

ESCAPED_STRING: /'[^']*'/ | /"[^"]*"/
%import common.CNAME
%import common.SIGNED_NUMBER
%import common.WS
%ignore WS
"""

_ODATA_PARSER_VAR: typing.Final[contextvars.ContextVar[Lark]] = contextvars.ContextVar("odata_parser")


# 🧠 Transformer: convert the tree into Python functions
class ODataTransformer(Transformer[typing.Any, typing.Any]):
    def value(self, token: list[Token]) -> typing.Any:
        val = token[0]
        if val.type == "ESCAPED_STRING":
            raw = val.value
            if raw.startswith("'") and raw.endswith("'"):
                return raw[1:-1]
            elif raw.startswith('"') and raw.endswith('"'):
                return raw[1:-1]
            else:
                raise ValueError(f"Formato de cadena no válido: {raw}")
        elif val.type == "SIGNED_NUMBER":
            return float(val.value) if '.' in val.value else int(val.value)

    def field(self, token: list[Token]) -> collections.abc.Callable[[dict[str, typing.Any]], typing.Any]:
        field_name = token[0].value
        return lambda item: item.get(field_name)

    def binary_op(self, items: list[typing.Any]) -> collections.abc.Callable[[dict[str, typing.Any]], bool]:
        left, op_token, right = items

        op = op_token.value if isinstance(op_token, Token) else op_token

        def resolve(expr: typing.Any) -> typing.Callable[[dict[str, typing.Any]], typing.Any]:
            if callable(expr):
                return expr
            else:
                return lambda _: expr  # fixed value

        left_fn = resolve(left)
        right_fn = resolve(right)

        match op:
            case "eq":
                return lambda item: left_fn(item) == right_fn(item)
            case "gt":
                return lambda item: left_fn(item) > right_fn(item)
            case "lt":
                return lambda item: left_fn(item) < right_fn(item)
            case "ne":
                return lambda item: left_fn(item) != right_fn(item)
            case "ge":
                return lambda item: left_fn(item) >= right_fn(item)
            case "le":
                return lambda item: left_fn(item) <= right_fn(item)
            case _:
                raise ValueError(f"Operador desconocido: {op}")

    def func_op(self, items: list[typing.Any]) -> collections.abc.Callable[[dict[str, typing.Any]], typing.Any]:
        func_token, field_fn, value = items

        func = func_token.value if isinstance(func_token, Token) else func_token

        match func:
            case "startswith":
                return lambda item: str(field_fn(item)).startswith(value)
            case "endswith":
                return lambda item: str(field_fn(item)).endswith(value)
            case "contains":
                # TODO: allow dicts and lists?
                return lambda item: str(value) in str(field_fn(item))
            case _:
                raise ValueError(f"Función desconocida: {func}")

    def value_func(
        self, items: list[typing.Any]
    ) -> collections.abc.Callable[[dict[str, typing.Any]], typing.Any]:
        func_token, field_fn = items
        func = func_token.value if isinstance(func_token, Token) else func_token

        match func:
            case "length":
                return lambda item: len(str(field_fn(item)))
            case "tolower":
                return lambda item: str(field_fn(item)).lower()
            case "toupper":
                return lambda item: str(field_fn(item)).upper()
            case "trim":
                return lambda item: str(field_fn(item)).strip()
            case _:
                raise ValueError(f"Value disconnected: {func}")

    def and_expr(
        self, items: list[collections.abc.Callable[..., typing.Any]]
    ) -> collections.abc.Callable[[dict[str, typing.Any]], bool]:
        left, right = items
        return lambda item: left(item) and right(item)

    def or_expr(
        self, items: list[collections.abc.Callable[..., typing.Any]]
    ) -> collections.abc.Callable[[dict[str, typing.Any]], bool]:
        left, right = items
        return lambda item: left(item) or right(item)

    def not_expr(
        self, items: list[collections.abc.Callable[..., typing.Any]]
    ) -> collections.abc.Callable[[dict[str, typing.Any]], bool]:
        expr = items[0]
        return lambda item: not expr(item)

    def expr(
        self, items: list[collections.abc.Callable[[dict[str, typing.Any]], bool]]
    ) -> collections.abc.Callable[[dict[str, typing.Any]], bool]:
        return items[0]

    def paren_expr(
        self, items: list[collections.abc.Callable[[dict[str, typing.Any]], bool]]
    ) -> collections.abc.Callable[[dict[str, typing.Any]], bool]:
        return items[0]


# _odata_parser: typing.Final[Lark] = Lark(_ODATA_GRAMMAR, parser="lalr", transformer=ODataTransformer())


def get_parser() -> Lark:
    try:
        return _ODATA_PARSER_VAR.get()
    except LookupError:
        parser = Lark(_ODATA_GRAMMAR, parser="lalr", transformer=ODataTransformer())
        _ODATA_PARSER_VAR.set(parser)
        return parser


# filter
def exec_filter(data: list[dict[str, typing.Any]], query: str) -> typing.Iterable[dict[str, typing.Any]]:
    try:
        filter_func = typing.cast(
            collections.abc.Callable[[dict[str, typing.Any]], bool], get_parser().parse(query)
        )
        return filter(filter_func, data)
    except Exception as e:
        raise ValueError(f"Error al procesar la query OData: {e}")
