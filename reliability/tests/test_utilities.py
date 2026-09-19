import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utilities import Invalid, calc, date_math, structured_parse, unit_convert


class Utilities(unittest.TestCase):
    def test_calculator(self):
        for expression, value in [
            ("17.5% of 840", "147"),
            ("(2 + 3)^4", "625"),
            ("0.1 + 0.2", "0.3"),
            ("sqrt(81)", "9"),
            ("round(2.345,2)", "2.34"),
            ("-2^2", "-4"),
        ]:
            self.assertEqual(calc(expression)["value"], value)

    def test_reject_code(self):
        for x in [
            "__import__('os').system('id')",
            "[1][0]",
            "2**100000000",
            "(lambda:1)()",
            "1/0",
            "True + 1",
        ]:
            with self.assertRaises(Exception):
                calc(x)

    def test_dates(self):
        self.assertEqual(
            date_math({"operation": "add", "date": "2026-01-01", "amount": 90})["date"],
            "2026-04-01",
        )
        self.assertEqual(
            date_math(
                {"operation": "between", "date": "2024-02-28", "other": "2024-03-01"}
            )["days"],
            2,
        )
        self.assertEqual(
            date_math(
                {
                    "operation": "add",
                    "date": "2024-01-31",
                    "amount": 1,
                    "unit": "months",
                }
            )["date"],
            "2024-02-29",
        )
        self.assertEqual(
            date_math({"operation": "weekday", "date": "2026-09-07"})["weekday"],
            "Monday",
        )

    def test_timezone_relative_dst(self):
        now = dt.datetime(2026, 1, 1, 1, tzinfo=dt.UTC)
        self.assertEqual(
            date_math(
                {
                    "operation": "resolve",
                    "date": "today",
                    "timezone": "America/Los_Angeles",
                },
                now,
            )["date"],
            "2025-12-31",
        )
        self.assertEqual(
            date_math(
                {
                    "operation": "convert_timezone",
                    "date": "2026-11-01T01:30:00-07:00",
                    "timezone": "UTC",
                }
            )["datetime"],
            "2026-11-01T08:30:00+00:00",
        )
        for p in [
            {"operation": "resolve", "date": "03/04/2026"},
            {
                "operation": "convert_timezone",
                "date": "2026-11-01T01:30:00",
                "timezone": "America/Los_Angeles",
            },
            {"operation": "now", "amount": 3},
        ]:
            with self.assertRaises(Exception):
                date_math(p)

    def test_units(self):
        for v, a, b, out in [
            (32, "F", "C", "0"),
            (100, "C", "F", "212"),
            (1, "mi", "km", "1.609344"),
            (1, "GiB", "GB", "1.073741824"),
            (1, "kWh", "J", "3600000"),
            (1, "lb", "kg", "0.45359237"),
        ]:
            self.assertEqual(
                unit_convert({"value": v, "from_unit": a, "to_unit": b})["value"], out
            )
        for a, b in [("gallon", "L"), ("m", "kg"), ("GB", "Gb")]:
            with self.assertRaises(Invalid):
                unit_convert({"value": 1, "from_unit": a, "to_unit": b})

    def test_parsing(self):
        self.assertTrue(
            structured_parse({"format": "json", "text": '{"a":[1,true]}'})["valid"]
        )
        self.assertEqual(
            structured_parse(
                {"format": "extract", "text": '{"a":[1,2]}', "path": "a.1"}
            )["value"],
            2,
        )
        self.assertEqual(
            structured_parse({"format": "csv", "text": 'a,b\n"x,y",z'})["rows"][1],
            ["x,y", "z"],
        )
        self.assertEqual(
            structured_parse(
                {"format": "url", "text": "https://example.com/x?a=1&a=2"}
            )["query"],
            [("a", "1"), ("a", "2")],
        )
        self.assertEqual(
            len(
                structured_parse(
                    {
                        "format": "regex",
                        "text": "abc 123 def 456",
                        "pattern": "[0-9][0-9][0-9]",
                    }
                )["matches"]
            ),
            2,
        )
        for p in [
            {"format": "json", "text": '{"a":1,"a":2}'},
            {"format": "json", "text": "NaN"},
            {"format": "regex", "text": "a" * 100, "pattern": "(a+)+$"},
            {"format": "url", "text": "https://user:password@example.com"},
        ]:
            with self.assertRaises(Exception):
                structured_parse(p)


if __name__ == "__main__":
    unittest.main()
