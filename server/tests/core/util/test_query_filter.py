import unittest

from uds.core.util.query_filter import exec_filter  # Ajusta esto al nombre real del archivo si lo separas


class TestQueryFilter(unittest.TestCase):
    def setUp(self):
        self.data = [
            {"name": "Alice", "age": 30},
            {"name": "Bob", "age": 25},
            {"name": "Charlie", "age": 35},
            {"name": "David", "age": 30},
        ]

    def test_eq_operator(self):
        result = list(exec_filter(self.data, "name eq 'Alice'"))
        self.assertEqual(result, [{"name": "Alice", "age": 30}])

    def test_gt_operator(self):
        result = list(exec_filter(self.data, "age gt 30"))
        self.assertEqual(result, [{"name": "Charlie", "age": 35}])

    def test_ge_operator(self):
        result = list(exec_filter(self.data, "age ge 30"))
        self.assertEqual(
            result,
            [
                {"name": "Alice", "age": 30},
                {"name": "Charlie", "age": 35},
                {"name": "David", "age": 30},
            ],
        )

    def test_ne_operator(self):
        result = list(exec_filter(self.data, "name ne 'Bob'"))
        self.assertEqual(
            result,
            [
                {"name": "Alice", "age": 30},
                {"name": "Charlie", "age": 35},
                {"name": "David", "age": 30},
            ],
        )

    def test_and_or_not(self):
        result = list(exec_filter(self.data, "age ge 30 and not name eq 'David'"))
        self.assertEqual(result, [{"name": "Alice", "age": 30}, {"name": "Charlie", "age": 35}])

    def test_startswith_func(self):
        result = list(exec_filter(self.data, "startswith(name,'A')"))
        self.assertEqual(result, [{"name": "Alice", "age": 30}])

    def test_grouped_expression_with_parentheses(self):
        query = "not (age gt 30 or name eq 'Bob')"
        result = list(exec_filter(self.data, query))
        # Esperamos solo a Alice y David, porque:
        # - Charlie tiene age > 30 → excluido
        # - Bob tiene name eq 'Bob' → excluido
        # - Alice y David tienen age == 30 y name != 'Bob' → incluidos
        expected = [
            {"name": "Alice", "age": 30},
            {"name": "David", "age": 30},
        ]
        self.assertEqual(result, expected)

    def test_endswith_function(self):
        query = "endswith(name,'e')"
        result = list(exec_filter(self.data, query))
        expected = [{"name": "Alice", "age": 30}, {"name": "Charlie", "age": 35}]
        self.assertEqual(result, expected)

    def test_unary_func_length(self):
        result = list(exec_filter(self.data, "length(name) eq 5"))
        expected = [{"name": "Alice", "age": 30}, {"name": "David", "age": 30}]
        self.assertEqual(result, expected)
