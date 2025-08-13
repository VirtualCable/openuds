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
        # We expect:
        # - Charlie has age > 30 → excluded
        # - Bob has name eq 'Bob' → excluded
        # - Alice and David have age == 30 and name != 'Bob' → included
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

    def test_toupper_function(self):
        result = list(exec_filter(self.data, "toupper(name) eq 'ALICE'"))
        expected = [{"name": "Alice", "age": 30}]
        self.assertEqual(result, expected)

    def test_tolower_function(self):
        result = list(exec_filter(self.data, "tolower(name) eq 'david'"))
        expected = [{"name": "David", "age": 30}]
        self.assertEqual(result, expected)

    def test_concat_function(self):
        data = [
            {"first": "John", "last": "Doe"},
            {"first": "Jane", "last": "Smith"},
        ]
        result = list(exec_filter(data, "concat(first,last) eq 'JohnDoe'"))
        expected = [{"first": "John", "last": "Doe"}]
        self.assertEqual(result, expected)

    def test_indexof_function_case_sensitive(self):
        result = list(exec_filter(self.data, "indexof(name,'a') ge 0"))
        expected = [
            {"name": "Charlie", "age": 35},
            {"name": "David", "age": 30},
        ]
        self.assertEqual(result, expected)
        
    def test_indexof_function_case_insensitive(self):
        result = list(exec_filter(self.data, "indexof(tolower(name),'a') ge 0"))
        expected = [
            {"name": "Alice", "age": 30},
            {"name": "Charlie", "age": 35},
            {"name": "David", "age": 30},
        ]
        self.assertEqual(result, expected)
        

    def test_substringof_function(self):
        result = list(exec_filter(self.data, "substringof('li',name)"))
        expected = [{"name": "Alice", "age": 30}, {"name": "Charlie", "age": 35}]
        self.assertEqual(result, expected)

    def test_year_function(self):
        data = [
            {"dob": "1990-05-12"},
            {"dob": "1985-11-30"},
        ]
        result = list(exec_filter(data, "year(dob) eq '1990'"))
        expected = [{"dob": "1990-05-12"}]
        self.assertEqual(result, expected)

    def test_month_function(self):
        data = [
            {"dob": "1990-05-12"},
            {"dob": "1985-11-30"},
        ]
        result = list(exec_filter(data, "month(dob) eq '11'"))
        expected = [{"dob": "1985-11-30"}]
        self.assertEqual(result, expected)

    def test_day_function(self):
        data = [
            {"dob": "1990-05-12"},
            {"dob": "1985-11-30"},
        ]
        result = list(exec_filter(data, "day(dob) eq '12'"))
        expected = [{"dob": "1990-05-12"}]
        self.assertEqual(result, expected)

    def test_nested_field_access(self):
        data = [
            {"user": {"name": "Alice"}},
            {"user": {"name": "Bob"}},
        ]
        result = list(exec_filter(data, "user.name eq 'Bob'"))
        expected = [{"user": {"name": "Bob"}}]
        self.assertEqual(result, expected)

    def test_not_with_parentheses(self):
        result = list(exec_filter(self.data, "not (name eq 'Alice')"))
        expected = [
            {"name": "Bob", "age": 25},
            {"name": "Charlie", "age": 35},
            {"name": "David", "age": 30},
        ]
        self.assertEqual(result, expected)
