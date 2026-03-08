#!/usr/bin/env python3

import json
import csv
import io
import sys
import xml.etree.ElementTree as ET
from collections import OrderedDict
from pathlib import Path

import xmltodict
import yaml
from toon import encode as toon_encode, decode as toon_decode


# ──────────────────────────────────────────────────────────────────────
#  Detection
# ──────────────────────────────────────────────────────────────────────

def detect_format(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith(("{", "[")):
        try:
            json.loads(stripped)
            return "json"
        except json.JSONDecodeError:
            pass
    if stripped.startswith("<"):
        try:
            ET.fromstring(stripped)
            return "xml"
        except ET.ParseError:
            pass
    try:
        json.loads(stripped)
        return "json"
    except Exception:
        pass
    try:
        ET.fromstring(stripped)
        return "xml"
    except Exception:
        pass
    raise ValueError("Could not detect input as JSON or XML.")


# ──────────────────────────────────────────────────────────────────────
#  Parsing → Python dict / list
# ──────────────────────────────────────────────────────────────────────

def parse_json(text: str):
    return json.loads(text)


def parse_xml(text: str):
    return xmltodict.parse(text)


# ──────────────────────────────────────────────────────────────────────
#  Serializers
# ──────────────────────────────────────────────────────────────────────

def to_json_pretty(data) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)


def to_json_compact(data) -> str:
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False)


def to_yaml_string(data) -> str | None:
    try:
        return yaml.dump(
            data, default_flow_style=False,
            allow_unicode=True, sort_keys=False,
        )
    except Exception:
        return None


def to_toon_string(data) -> str | None:
    """Encode data as TOON. Returns None if the library cannot handle it."""
    try:
        result = toon_encode(data)
        # TOON encodes empty containers (e.g. {}) as "", which can't be decoded
        if not result:
            return None
        return result
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────────────
#  CSV — type-preserving serialization
# ──────────────────────────────────────────────────────────────────────

TYPE_MAP = {int: "int", float: "float", bool: "bool", str: "str"}


def _csv_encode_value(val) -> str:
    if val is None:
        return ""
    if isinstance(val, bool):
        return "true" if val else "false"
    return str(val)


def _csv_decode_value(raw: str, type_hint: str):
    if raw == "" and type_hint != "str":
        return None
    if type_hint == "int":
        return int(raw)
    if type_hint == "float":
        return float(raw)
    if type_hint == "bool":
        return raw.lower() == "true"
    return raw


def _detect_column_types(rows: list[dict]) -> dict[str, str]:
    types = {}
    for key in rows[0].keys():
        samples = [row[key] for row in rows if row[key] is not None]
        if not samples:
            types[key] = "str"
        else:
            types[key] = TYPE_MAP.get(type(samples[0]), "str")
    return types


def to_csv_string(data) -> str | None:
    rows = _extract_flat_rows(data)
    if rows is None:
        return None

    fieldnames = list(rows[0].keys())
    col_types = _detect_column_types(rows)

    buf = io.StringIO()
    type_hints = ",".join(col_types[f] for f in fieldnames)
    buf.write(f"#types:{type_hints}\n")

    writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: _csv_encode_value(v) for k, v in row.items()})
    return buf.getvalue()


def parse_csv_string(text: str) -> list[dict]:
    stream = io.StringIO(text.strip())

    # Peek at first line for #types header
    first_line = stream.readline()
    type_hints_list = None
    if first_line.startswith("#types:"):
        type_hints_list = first_line.strip()[len("#types:"):].split(",")
    else:
        # Not a types line — rewind so DictReader sees the header
        stream.seek(0)

    reader = csv.DictReader(stream)
    fieldnames = reader.fieldnames or []
    type_hints = dict(zip(fieldnames, type_hints_list)) if type_hints_list else {}

    result = []
    for row in reader:
        decoded = {}
        for key, raw_val in row.items():
            if key in type_hints:
                decoded[key] = _csv_decode_value(raw_val, type_hints[key])
            else:
                decoded[key] = _guess_type(raw_val)
        result.append(decoded)
    return result


def _guess_type(val: str):
    if val == "":
        return None
    if val.lower() in ("true", "false"):
        return val.lower() == "true"
    try:
        return int(val)
    except ValueError:
        pass
    try:
        return float(val)
    except ValueError:
        pass
    return val


def _extract_flat_rows(data) -> list[dict] | None:
    if isinstance(data, list):
        return _validate_flat_dicts(data)
    if isinstance(data, dict) and len(data) == 1:
        val = next(iter(data.values()))
        if isinstance(val, list):
            return _validate_flat_dicts(val)
    return None


def _validate_flat_dicts(lst: list) -> list[dict] | None:
    if not lst:
        return None
    if not all(isinstance(item, dict) for item in lst):
        return None
    keys = set(lst[0].keys())
    for item in lst:
        if set(item.keys()) != keys:
            return None
        for v in item.values():
            if isinstance(v, (dict, list)):
                return None
    return lst


# ──────────────────────────────────────────────────────────────────────
#  Deserializers (for round-trip verification)
# ──────────────────────────────────────────────────────────────────────

def from_json(text: str):
    return json.loads(text)


def from_yaml(text: str):
    return yaml.safe_load(text)


def from_toon(text: str):
    return toon_decode(text)


def from_csv(text: str) -> list[dict]:
    return parse_csv_string(text)


# ──────────────────────────────────────────────────────────────────────
#  Main pipeline
# ──────────────────────────────────────────────────────────────────────

SEPARATOR = "─" * 60


def build_candidates(data) -> OrderedDict:
    """Generate all format conversions from parsed data."""
    candidates: OrderedDict[str, str] = OrderedDict()
    candidates["JSON (pretty)"]  = to_json_pretty(data)
    candidates["JSON (compact)"] = to_json_compact(data)

    yaml_out = to_yaml_string(data)
    if yaml_out is not None:
        candidates["YAML"] = yaml_out

    toon_out = to_toon_string(data)
    if toon_out is not None:
        candidates["TOON"] = toon_out

    csv_out = to_csv_string(data)
    if csv_out is not None:
        candidates["CSV"] = csv_out

    return candidates


def run(input_path: str = "input", output_path: str = "output"):
    path = Path(input_path)
    if not path.exists():
        print(f"ERROR: '{input_path}' not found.")
        sys.exit(1)

    raw = path.read_text(encoding="utf-8")
    original_len = len(raw)

    fmt = detect_format(raw)
    print(f"Detected input format : {fmt.upper()}")
    print(f"Original size         : {original_len:,} characters")
    print(SEPARATOR)

    data = parse_json(raw) if fmt == "json" else parse_xml(raw)
    candidates = build_candidates(data)

    print(f"{'Format':<20} {'Characters':>12}  {'vs Original':>12}")
    print(SEPARATOR)

    best_name = None
    best_len = float("inf")
    best_text = ""

    for name, text in candidates.items():
        length = len(text)
        diff = length - original_len
        pct = (diff / original_len) * 100 if original_len else 0
        if length < best_len:
            best_len = length
            best_name = name
            best_text = text
        sign = "+" if diff > 0 else ""
        print(f"  {name:<18} {length:>10,}  {sign}{diff:>11,}  ({sign}{pct:.1f}%)")

    print(SEPARATOR)
    savings = original_len - best_len
    savings_pct = (savings / original_len) * 100 if original_len else 0
    print(f"★  Best format: {best_name}  ({best_len:,} chars, saves {savings:,} / {savings_pct:.1f}%)")

    Path(output_path).write_text(best_text, encoding="utf-8")
    print(f"\n   Output written to: {output_path}")


if __name__ == "__main__":
    input_file  = sys.argv[1] if len(sys.argv) > 1 else "input"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "output"
    run(input_file, output_file)