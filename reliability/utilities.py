"""Bounded standard-library utilities. JSON stdin/stdout only; no dynamic execution."""

import ast
import calendar
import csv
import datetime as dt
import io
import json
import re
import sys
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal, localcontext
from urllib.parse import parse_qsl, urlsplit
from zoneinfo import ZoneInfo


class Invalid(ValueError):
    pass


def number(value):
    if isinstance(value, bool):
        raise Invalid("INVALID_NUMBER")
    d = Decimal(str(value))
    if not d.is_finite() or (d and abs(d.adjusted()) > 1000):
        raise Invalid("NUMERIC_LIMIT")
    return d


def display(value):
    if not value.is_finite() or (value and abs(value.adjusted()) > 1000):
        raise Invalid("NUMERIC_LIMIT")
    return format(value.normalize(), "f") if value else "0"


def calc(expression):
    if not isinstance(expression, str) or not 0 < len(expression) <= 512:
        raise Invalid("EXPRESSION_LIMIT")
    text = re.sub(r"(\d+(?:\.\d+)?)\s*%\s+of\s+", r"(\1/100)*", expression, flags=re.I)
    text = re.sub(r"(\d+(?:\.\d+)?)\s*%", r"(\1/100)", text).replace("^", "**")
    tree = ast.parse(text, mode="eval")
    if sum(1 for _ in ast.walk(tree)) > 128:
        raise Invalid("EXPRESSION_LIMIT")

    def walk(n, depth=0):
        if depth > 24:
            raise Invalid("EXPRESSION_LIMIT")
        if isinstance(n, ast.Constant) and type(n.value) in (int, float):
            return number(ast.get_source_segment(text, n))
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.UAdd, ast.USub)):
            x = walk(n.operand, depth + 1)
            return x if isinstance(n.op, ast.UAdd) else -x
        if isinstance(n, ast.BinOp):
            a, b = walk(n.left, depth + 1), walk(n.right, depth + 1)
            if isinstance(n.op, ast.Add):
                r = a + b
            elif isinstance(n.op, ast.Sub):
                r = a - b
            elif isinstance(n.op, ast.Mult):
                r = a * b
            elif isinstance(n.op, ast.Div):
                r = a / b
            elif isinstance(n.op, ast.Pow):
                if b != int(b) or abs(b) > 1000:
                    raise Invalid("EXPONENT_LIMIT")
                r = a ** int(b)
            else:
                raise Invalid("UNSUPPORTED_OPERATION")
            return number(r)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and not n.keywords:
            args = [walk(x, depth + 1) for x in n.args]
            if n.func.id in ("min", "max") and 1 <= len(args) <= 16:
                return (min if n.func.id == "min" else max)(args)
            if len(args) == 1:
                if n.func.id == "abs":
                    return abs(args[0])
                if n.func.id == "sqrt":
                    return args[0].sqrt()
                if n.func.id == "floor":
                    return args[0].to_integral_value(rounding=ROUND_FLOOR)
                if n.func.id == "ceil":
                    return args[0].to_integral_value(rounding=ROUND_CEILING)
                if n.func.id == "round":
                    return args[0].to_integral_value()
            if (
                n.func.id == "round"
                and len(args) == 2
                and args[1] == int(args[1])
                and abs(args[1]) <= 100
            ):
                return args[0].quantize(Decimal(1).scaleb(-int(args[1])))
        raise Invalid("UNSUPPORTED_EXPRESSION")

    with localcontext() as c:
        c.prec = 50
        result = walk(tree.body)
        return {
            "value": display(result),
            "precision_digits": 50,
            "rounding": "half_even",
        }


def date_value(value, zone, reference):
    if not isinstance(value, str):
        raise Invalid("INVALID_DATE")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return dt.date.fromisoformat(value)
    today = reference.astimezone(zone).date()
    if value in ("today", "tomorrow", "yesterday"):
        return today + dt.timedelta(
            days={"today": 0, "tomorrow": 1, "yesterday": -1}[value]
        )
    m = re.fullmatch(r"(?:in (\d{1,4}) days|(\d{1,4}) days ago)", value)
    if m:
        return today + dt.timedelta(days=int(m[1]) if m[1] else -int(m[2]))
    raise Invalid("AMBIGUOUS_DATE")


def date_math(p, now=None):
    zone = ZoneInfo(p.get("timezone", "UTC"))
    now = now or dt.datetime.now(dt.UTC)
    if "reference" in p:
        now = dt.datetime.fromisoformat(p["reference"].replace("Z", "+00:00"))
        if now.tzinfo is None:
            raise Invalid("OFFSET_REQUIRED")
    op = p["operation"]
    out = {"timezone": str(zone)}
    allowed = {
        "now": set(),
        "add": {"date", "amount", "unit"},
        "between": {"date", "other"},
        "weekday": {"date"},
        "resolve": {"date"},
        "convert_timezone": {"date"},
    }
    if op not in allowed or set(p) - (
        {"operation", "timezone", "reference"} | allowed[op]
    ):
        raise Invalid("UNUSED_ARGUMENT")
    if op == "now":
        return {**out, "datetime": now.astimezone(zone).isoformat()}
    if op == "convert_timezone":
        instant = dt.datetime.fromisoformat(p["date"].replace("Z", "+00:00"))
        if instant.tzinfo is None:
            raise Invalid("OFFSET_REQUIRED")
        return {**out, "datetime": instant.astimezone(zone).isoformat()}
    date = date_value(p["date"], zone, now)
    if op == "between":
        return {**out, "days": (date_value(p["other"], zone, now) - date).days}
    if op == "weekday":
        return {**out, "date": date.isoformat(), "weekday": date.strftime("%A")}
    if op == "resolve":
        return {**out, "date": date.isoformat(), "reference": now.isoformat()}
    amount = p["amount"]
    unit = p.get("unit", "days")
    if type(amount) is not int or abs(amount) > 10000:
        raise Invalid("DATE_RANGE")
    clamped = False
    if unit == "months":
        total = date.year * 12 + date.month - 1 + amount
        year, month = divmod(total, 12)
        month += 1
        day = min(date.day, calendar.monthrange(year, month)[1])
        clamped = day != date.day
        date = date.replace(year=year, month=month, day=day)
    elif unit in ("days", "weeks"):
        date += dt.timedelta(days=amount * (7 if unit == "weeks" else 1))
    else:
        raise Invalid("UNSUPPORTED_DATE_UNIT")
    return {**out, "date": date.isoformat(), "month_end_clamped": clamped}


# Factors are exact decimal definitions relative to a unit in the same dimension.
UNITS = {}


def units(dimension, values):
    for names, factor in values:
        for name in names.split("|"):
            UNITS[name] = (dimension, Decimal(factor))


units(
    "distance",
    [
        ("m|meter|meters", "1"),
        ("km|kilometer|kilometers", "1000"),
        ("cm", "0.01"),
        ("mm", "0.001"),
        ("mi|mile|miles", "1609.344"),
        ("ft|foot|feet", "0.3048"),
        ("in|inch|inches", "0.0254"),
        ("yd|yard|yards", "0.9144"),
    ],
)
units(
    "mass",
    [
        ("kg|kilogram|kilograms", "1"),
        ("g|gram|grams", "0.001"),
        ("mg", "0.000001"),
        ("lb|pound|pounds", "0.45359237"),
        ("oz|ounce|ounces", "0.028349523125"),
    ],
)
units(
    "volume",
    [
        ("L|liter|liters", "1"),
        ("mL", "0.001"),
        ("m3", "1000"),
        ("US_gallon", "3.785411784"),
        ("imperial_gallon", "4.54609"),
        ("US_cup", "0.2365882365"),
    ],
)
units(
    "area",
    [
        ("m2", "1"),
        ("km2", "1000000"),
        ("ft2", "0.09290304"),
        ("acre", "4046.8564224"),
        ("hectare", "10000"),
    ],
)
units(
    "speed",
    [
        ("m/s", "1"),
        ("km/h", "0.27777777777777777777777777777777777777777777777778"),
        ("mph", "0.44704"),
    ],
)
units(
    "storage",
    [
        ("B|byte|bytes", "1"),
        ("kB|KB", "1000"),
        ("MB", "1000000"),
        ("GB", "1000000000"),
        ("TB", "1000000000000"),
        ("KiB", "1024"),
        ("MiB", "1048576"),
        ("GiB", "1073741824"),
        ("TiB", "1099511627776"),
        ("bit", "0.125"),
    ],
)
units(
    "time",
    [
        ("s|second|seconds", "1"),
        ("ms", "0.001"),
        ("min|minute|minutes", "60"),
        ("h|hour|hours", "3600"),
        ("day|days", "86400"),
        ("week|weeks", "604800"),
    ],
)
units(
    "pressure",
    [
        ("Pa", "1"),
        ("kPa", "1000"),
        ("MPa", "1000000"),
        ("bar", "100000"),
        ("atm", "101325"),
    ],
)
units("energy", [("J", "1"), ("kJ", "1000"), ("Wh", "3600"), ("kWh", "3600000")])
units("power", [("W", "1"), ("kW", "1000"), ("MW", "1000000")])
units("force", [("N", "1"), ("kN", "1000")])
units(
    "frequency",
    [("Hz", "1"), ("kHz", "1000"), ("MHz", "1000000"), ("GHz", "1000000000")],
)
units("voltage", [("V", "1"), ("mV", "0.001"), ("kV", "1000")])
units("current", [("A", "1"), ("mA", "0.001")])
units("resistance", [("ohm", "1"), ("kohm", "1000"), ("Mohm", "1000000")])
TEMP = {
    "C": "C",
    "celsius": "C",
    "Celsius": "C",
    "F": "F",
    "fahrenheit": "F",
    "Fahrenheit": "F",
    "K": "K",
    "kelvin": "K",
}


def unit_convert(p):
    a, b = p["from_unit"], p["to_unit"]
    value = number(p["value"])
    with localcontext() as c:
        c.prec = 50
        if a in TEMP and b in TEMP:
            a, b = TEMP[a], TEMP[b]
            kelvin = (
                value
                if a == "K"
                else (
                    (value - 32) * Decimal(5) / 9 + Decimal("273.15")
                    if a == "F"
                    else value + Decimal("273.15")
                )
            )
            if kelvin < 0:
                raise Invalid("BELOW_ABSOLUTE_ZERO")
            result = (
                kelvin
                if b == "K"
                else (
                    (kelvin - Decimal("273.15")) * 9 / 5 + 32
                    if b == "F"
                    else kelvin - Decimal("273.15")
                )
            )
        else:
            if a not in UNITS or b not in UNITS:
                raise Invalid("UNKNOWN_OR_AMBIGUOUS_UNIT")
            da, fa = UNITS[a]
            db, fb = UNITS[b]
            if da != db:
                raise Invalid("INCOMPATIBLE_UNITS")
            result = value * fa / fb
        return {"value": display(result), "unit": p["to_unit"], "precision_digits": 50}


def strict_json(text):
    def pairs(items):
        d = {}
        for k, v in items:
            if k in d:
                raise Invalid("DUPLICATE_JSON_KEY")
            d[k] = v
        return d

    def bad(_):
        raise Invalid("NONFINITE_JSON")

    return json.loads(text, object_pairs_hook=pairs, parse_constant=bad)


def structured_parse(p):
    text = p["text"]
    op = p["format"]
    if "headers" in p and op not in ("csv", "tsv"):
        raise Invalid("UNUSED_ARGUMENT")
    if len(text.encode()) > 32768:
        raise Invalid("INPUT_LIMIT")
    if op in ("json", "extract"):
        obj = strict_json(text)
        if op == "extract":
            for key in p["path"].split("."):
                if not key or key in ("__proto__", "constructor", "prototype"):
                    raise Invalid("INVALID_KEY_PATH")
                obj = (
                    obj[int(key)]
                    if isinstance(obj, list) and key.isdigit()
                    else obj[key]
                )
        elif "path" in p:
            raise Invalid("UNUSED_ARGUMENT")
        return {"valid": True, "value": obj}
    if "path" in p:
        raise Invalid("UNUSED_ARGUMENT")
    if op == "url":
        u = urlsplit(text)
        if (
            u.scheme not in ("http", "https")
            or not u.hostname
            or u.username
            or u.password
        ):
            raise Invalid("INVALID_URL")
        return {
            "scheme": u.scheme,
            "hostname": u.hostname,
            "port": u.port,
            "path": u.path,
            "query": parse_qsl(u.query, keep_blank_values=True),
            "fragment": u.fragment,
        }
    if op in ("csv", "tsv"):
        rows = list(
            csv.reader(
                io.StringIO(text, newline=""),
                delimiter="," if op == "csv" else "\t",
                strict=True,
            )
        )
        if p.get("headers"):
            if not rows:
                raise Invalid("MISSING_HEADER")
            header = rows.pop(0)
            if len(set(header)) != len(header) or any(
                len(row) != len(header) for row in rows
            ):
                raise Invalid("AMBIGUOUS_COLUMNS")
            rows = [dict(zip(header, row, strict=False)) for row in rows]
        return {
            "rows": rows[:100],
            "total_rows": len(rows),
            "truncated": len(rows) > 100,
        }
    if op == "regex":
        pattern = p["pattern"]
        # Fixed-width patterns only; no repetition, groups, alternation or backreferences.
        if len(pattern) > 128 or re.search(r"[()*+?{}|\\]", pattern):
            raise Invalid("UNSAFE_REGEX")
        found = list(re.finditer(pattern, text))
        return {
            "matches": [
                {"text": m.group(), "start": m.start(), "end": m.end()}
                for m in found[:100]
            ],
            "truncated": len(found) > 100,
        }
    raise Invalid("UNSUPPORTED_FORMAT")


def execute(tool, args):
    if tool == "calc":
        return calc(args["expression"])
    if tool == "date_math":
        return date_math(args)
    if tool == "unit_convert":
        return unit_convert(args)
    if tool == "structured_parse":
        return structured_parse(args)
    raise Invalid("UNKNOWN_UTILITY")


if __name__ == "__main__":
    try:
        raw = sys.stdin.buffer.read(65537)
        if len(raw) > 65536:
            raise Invalid("INPUT_LIMIT")
        request = strict_json(raw)
        result = execute(request["tool"], request["args"])
        print(
            json.dumps(
                {"ok": True, "source": request["tool"], "data": result},
                ensure_ascii=False,
                allow_nan=False,
            )
        )
    except Exception as e:
        code = str(e) if isinstance(e, Invalid) else "INVALID_ARGUMENT"
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": {
                        "code": code,
                        "message": "Provide unambiguous supported arguments; no operation was performed.",
                    },
                }
            )
        )
