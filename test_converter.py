#!/usr/bin/env python3

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
import converter as conv


# ══════════════════════════════════════════════════════════════════════
#  Test data fixtures
# ══════════════════════════════════════════════════════════════════════

EMPLOYEES = {
    "employees": [
        {"id": 1, "name": "Alice Johnson",  "department": "Engineering", "salary": 95000,  "active": True},
        {"id": 2, "name": "Bob Smith",      "department": "Marketing",   "salary": 78000,  "active": True},
        {"id": 3, "name": "Carol White",    "department": "Engineering", "salary": 102000, "active": False},
        {"id": 4, "name": "David Brown",    "department": "Sales",       "salary": 67000,  "active": True},
    ]
}

FLAT_LIST = [
    {"city": "Stockholm",  "population": 975000, "capital": True},
    {"city": "Gothenburg", "population": 590000, "capital": False},
    {"city": "Malmö",      "population": 350000, "capital": False},
]

NESTED_CONFIG = {
    "app": {
        "name": "TestApp",
        "version": "1.0.0",
        "debug": False,
    },
    "database": {
        "host": "localhost",
        "port": 5432,
        "name": "mydb",
    },
}

MIXED_TYPES = {
    "items": [
        {"label": "alpha",   "value": 3.14,  "count": 10,  "enabled": True},
        {"label": "beta",    "value": 2.72,  "count": 20,  "enabled": False},
        {"label": "gamma",   "value": 1.62,  "count": 30,  "enabled": True},
    ]
}

UNICODE_DATA = {
    "greetings": [
        {"lang": "Swedish",  "text": "Hej världen",  "code": 1},
        {"lang": "Japanese", "text": "こんにちは世界",  "code": 2},
        {"lang": "Arabic",   "text": "مرحبا بالعالم", "code": 3},
    ]
}

SINGLE_ROW = {
    "records": [
        {"id": 42, "status": "ok", "score": 99.5, "verified": True}
    ]
}

MIXED_STRUCTURE = {
    "system": {
        "name": "ShopSphere",
        "version": "3.4.2",
        "environment": "production",
        "generatedAt": "2026-03-07T14:22:18Z",
    },
    "analytics": {
        "topCategories": [
            {"name": "electronics", "revenue": 1203344},
            {"name": "fitness",     "revenue": 842112},
        ]
    },
}

LIST_WITH_METADATA = {
    "count": 3,
    "page": 1,
    "results": [
        {"id": 1, "title": "Alpha"},
        {"id": 2, "title": "Beta"},
        {"id": 3, "title": "Gamma"},
    ],
}

DEEP_NESTING = {"a": {"b": {"c": {"d": {"e": "deep"}, "f": 42}}}}


# ══════════════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════════════

def normalize(obj):
    """Recursively normalize for comparison (sort dict keys)."""
    if isinstance(obj, dict):
        return {k: normalize(v) for k, v in sorted(obj.items())}
    if isinstance(obj, (list, tuple)):
        return [normalize(i) for i in obj]
    return obj


# ══════════════════════════════════════════════════════════════════════
#  Tests — Format Detection
# ══════════════════════════════════════════════════════════════════════

class TestFormatDetection(unittest.TestCase):

    def test_json_object(self):
        self.assertEqual(conv.detect_format('{"a": 1}'), "json")

    def test_json_array(self):
        self.assertEqual(conv.detect_format('[1, 2, 3]'), "json")

    def test_json_with_whitespace(self):
        self.assertEqual(conv.detect_format('  \n  {"key": "val"}  '), "json")

    def test_xml(self):
        self.assertEqual(conv.detect_format('<root><a>1</a></root>'), "xml")

    def test_xml_with_declaration(self):
        self.assertEqual(conv.detect_format('<?xml version="1.0"?>\n<root/>'), "xml")

    def test_invalid_raises(self):
        with self.assertRaises(ValueError):
            conv.detect_format("not json or xml")


# ══════════════════════════════════════════════════════════════════════
#  Tests — JSON Round-Trip
# ══════════════════════════════════════════════════════════════════════

class TestJsonRoundTrip(unittest.TestCase):

    def _check(self, data):
        self.assertEqual(conv.from_json(conv.to_json_pretty(data)),  data)
        self.assertEqual(conv.from_json(conv.to_json_compact(data)), data)

    def test_employees(self):       self._check(EMPLOYEES)
    def test_flat_list(self):       self._check(FLAT_LIST)
    def test_nested_config(self):   self._check(NESTED_CONFIG)
    def test_mixed_types(self):     self._check(MIXED_TYPES)
    def test_unicode(self):         self._check(UNICODE_DATA)
    def test_single_row(self):      self._check(SINGLE_ROW)
    def test_deep_nesting(self):    self._check(DEEP_NESTING)
    def test_mixed_structure(self):  self._check(MIXED_STRUCTURE)

    def test_compact_is_shorter(self):
        self.assertLess(len(conv.to_json_compact(EMPLOYEES)),
                        len(conv.to_json_pretty(EMPLOYEES)))


# ══════════════════════════════════════════════════════════════════════
#  Tests — YAML Round-Trip
# ══════════════════════════════════════════════════════════════════════

class TestYamlRoundTrip(unittest.TestCase):

    def _check(self, data):
        yaml_str = conv.to_yaml_string(data)
        self.assertIsNotNone(yaml_str)
        self.assertEqual(normalize(conv.from_yaml(yaml_str)), normalize(data))

    def test_employees(self):       self._check(EMPLOYEES)
    def test_flat_list(self):       self._check(FLAT_LIST)
    def test_nested_config(self):   self._check(NESTED_CONFIG)
    def test_mixed_types(self):     self._check(MIXED_TYPES)
    def test_unicode(self):         self._check(UNICODE_DATA)
    def test_deep_nesting(self):    self._check(DEEP_NESTING)
    def test_mixed_structure(self):  self._check(MIXED_STRUCTURE)


# ══════════════════════════════════════════════════════════════════════
#  Tests — TOON Round-Trip
# ══════════════════════════════════════════════════════════════════════

class TestToonRoundTrip(unittest.TestCase):
    """TOON must losslessly round-trip all data shapes."""

    def _check(self, data):
        toon_str = conv.to_toon_string(data)
        self.assertIsNotNone(toon_str, f"to_toon_string returned None")
        recovered = conv.from_toon(toon_str)
        self.assertEqual(normalize(recovered), normalize(data),
                         f"TOON round-trip mismatch.\nTOON:\n{toon_str}")

    def test_employees(self):       self._check(EMPLOYEES)
    def test_flat_list(self):       self._check(FLAT_LIST)
    def test_nested_config(self):   self._check(NESTED_CONFIG)
    def test_mixed_types(self):     self._check(MIXED_TYPES)
    def test_unicode(self):         self._check(UNICODE_DATA)
    def test_single_row(self):      self._check(SINGLE_ROW)
    def test_deep_nesting(self):    self._check(DEEP_NESTING)
    def test_mixed_structure(self):  self._check(MIXED_STRUCTURE)
    def test_list_with_metadata(self): self._check(LIST_WITH_METADATA)

    def test_toon_beats_json_compact_for_tabular(self):
        """TOON should be shorter than JSON compact for uniform arrays."""
        toon_str = conv.to_toon_string(EMPLOYEES)
        json_str = conv.to_json_compact(EMPLOYEES)
        self.assertLess(len(toon_str), len(json_str),
                        "TOON should beat JSON compact for tabular data")

    def test_toon_beats_json_compact_for_mixed(self):
        """TOON should be shorter than JSON compact for mixed structures."""
        toon_str = conv.to_toon_string(MIXED_STRUCTURE)
        json_str = conv.to_json_compact(MIXED_STRUCTURE)
        self.assertLess(len(toon_str), len(json_str),
                        "TOON should beat JSON compact for mixed data")

    def test_toon_preserves_booleans(self):
        data = {"items": [{"flag": True}, {"flag": False}]}
        recovered = conv.from_toon(conv.to_toon_string(data))
        self.assertIs(recovered["items"][0]["flag"], True)
        self.assertIs(recovered["items"][1]["flag"], False)

    def test_toon_preserves_integers(self):
        data = {"rows": [{"x": 0}, {"x": 999999}]}
        recovered = conv.from_toon(conv.to_toon_string(data))
        self.assertEqual(recovered["rows"][0]["x"], 0)
        self.assertEqual(recovered["rows"][1]["x"], 999999)

    def test_toon_preserves_floats(self):
        data = {"rows": [{"pi": 3.14}, {"e": 2.72}]}
        recovered = conv.from_toon(conv.to_toon_string(data))
        self.assertAlmostEqual(recovered["rows"][0]["pi"], 3.14)
        self.assertAlmostEqual(recovered["rows"][1]["e"], 2.72)

    def test_toon_preserves_null(self):
        data = {"val": None}
        recovered = conv.from_toon(conv.to_toon_string(data))
        self.assertIsNone(recovered["val"])


# ══════════════════════════════════════════════════════════════════════
#  Tests — CSV Round-Trip
# ══════════════════════════════════════════════════════════════════════

class TestCsvRoundTrip(unittest.TestCase):

    def _check(self, data, expected_rows):
        csv_str = conv.to_csv_string(data)
        self.assertIsNotNone(csv_str)
        self.assertTrue(csv_str.startswith("#types:"))
        recovered = conv.from_csv(csv_str)
        self.assertEqual(len(recovered), len(expected_rows))
        for orig, rec in zip(expected_rows, recovered):
            for key in orig:
                self.assertEqual(rec[key], orig[key],
                    f"Key '{key}': expected {orig[key]!r} ({type(orig[key]).__name__}), "
                    f"got {rec[key]!r} ({type(rec[key]).__name__})")
                self.assertIsInstance(rec[key], type(orig[key]))

    def test_employees(self):     self._check(EMPLOYEES, EMPLOYEES["employees"])
    def test_flat_list(self):     self._check(FLAT_LIST, FLAT_LIST)
    def test_mixed_types(self):   self._check(MIXED_TYPES, MIXED_TYPES["items"])
    def test_unicode(self):       self._check(UNICODE_DATA, UNICODE_DATA["greetings"])
    def test_single_row(self):    self._check(SINGLE_ROW, SINGLE_ROW["records"])

    def test_booleans_are_lowercase(self):
        csv_str = conv.to_csv_string(EMPLOYEES)
        body = csv_str.split("\n", 1)[1]
        self.assertIn("true", body)
        self.assertIn("false", body)
        self.assertNotIn("True", body)
        self.assertNotIn("False", body)

    def test_integers_survive(self):
        recovered = conv.from_csv(conv.to_csv_string(EMPLOYEES))
        for row in recovered:
            self.assertIsInstance(row["id"], int)
            self.assertIsInstance(row["salary"], int)

    def test_floats_survive(self):
        recovered = conv.from_csv(conv.to_csv_string(MIXED_TYPES))
        for row in recovered:
            self.assertIsInstance(row["value"], float)

    def test_csv_no_crlf(self):
        self.assertNotIn("\r\n", conv.to_csv_string(EMPLOYEES))

    # ── Data-loss prevention ──

    def test_mixed_structure_rejected(self):
        self.assertIsNone(conv.to_csv_string(MIXED_STRUCTURE))

    def test_list_with_metadata_rejected(self):
        self.assertIsNone(conv.to_csv_string(LIST_WITH_METADATA))

    def test_nested_data_rejected(self):
        self.assertIsNone(conv.to_csv_string(NESTED_CONFIG))

    def test_deep_nesting_rejected(self):
        self.assertIsNone(conv.to_csv_string(DEEP_NESTING))

    def test_empty_list_rejected(self):
        self.assertIsNone(conv.to_csv_string({"items": []}))

    def test_two_level_nested_rejected(self):
        data = {"meta": {"src": "api"}, "data": {"items": [{"x": 1}, {"x": 2}]}}
        self.assertIsNone(conv.to_csv_string(data))

    def test_single_key_wrapper_accepted(self):
        self.assertIsNotNone(conv.to_csv_string({"rows": [{"a": 1}, {"a": 2}]}))

    def test_bare_list_accepted(self):
        self.assertIsNotNone(conv.to_csv_string([{"a": 1}, {"a": 2}]))


# ══════════════════════════════════════════════════════════════════════
#  Tests — build_candidates
# ══════════════════════════════════════════════════════════════════════

class TestBuildCandidates(unittest.TestCase):

    def test_tabular_includes_csv(self):
        self.assertIn("CSV", conv.build_candidates(EMPLOYEES))

    def test_tabular_includes_toon(self):
        self.assertIn("TOON", conv.build_candidates(EMPLOYEES))

    def test_nested_excludes_csv(self):
        self.assertNotIn("CSV", conv.build_candidates(NESTED_CONFIG))

    def test_mixed_structure_excludes_csv(self):
        self.assertNotIn("CSV", conv.build_candidates(MIXED_STRUCTURE))

    def test_mixed_structure_includes_toon(self):
        """TOON handles mixed structures that CSV cannot."""
        self.assertIn("TOON", conv.build_candidates(MIXED_STRUCTURE))

    def test_removed_xml_and_toml(self):
        """XML and TOML should no longer appear as candidates."""
        for data in [EMPLOYEES, NESTED_CONFIG, MIXED_STRUCTURE, DEEP_NESTING]:
            cands = conv.build_candidates(data)
            for name in cands:
                self.assertNotIn("XML", name)
                self.assertNotIn("TOML", name)

    def test_all_core_formats_present(self):
        cands = conv.build_candidates(EMPLOYEES)
        for fmt in ["JSON (pretty)", "JSON (compact)", "YAML", "TOON"]:
            self.assertIn(fmt, cands)

    def test_all_values_nonempty(self):
        for data in [EMPLOYEES, NESTED_CONFIG, MIXED_STRUCTURE]:
            for name, text in conv.build_candidates(data).items():
                self.assertGreater(len(text), 0, f"{name} is empty")


# ══════════════════════════════════════════════════════════════════════
#  Tests — Full Pipeline (end-to-end)
# ══════════════════════════════════════════════════════════════════════

class TestFullPipeline(unittest.TestCase):

    def _run_pipeline(self, input_data_str):
        with tempfile.TemporaryDirectory() as tmpdir:
            inp = Path(tmpdir) / "input"
            out = Path(tmpdir) / "output"
            inp.write_text(input_data_str, encoding="utf-8")
            conv.run(str(inp), str(out))
            self.assertTrue(out.exists(), "Output file was not created")
            return out.read_text(encoding="utf-8")

    def test_json_input_produces_output(self):
        result = self._run_pipeline(json.dumps(EMPLOYEES, indent=2))
        self.assertGreater(len(result), 0)

    def test_json_list_input(self):
        result = self._run_pipeline(json.dumps(FLAT_LIST, indent=2))
        self.assertGreater(len(result), 0)

    def test_output_is_smallest(self):
        input_str = json.dumps(EMPLOYEES, indent=2)
        with tempfile.TemporaryDirectory() as tmpdir:
            inp = Path(tmpdir) / "input"
            out = Path(tmpdir) / "output"
            inp.write_text(input_str, encoding="utf-8")
            conv.run(str(inp), str(out))
            output_len = len(out.read_text(encoding="utf-8"))
            data = json.loads(input_str)
            min_len = min(len(t) for t in conv.build_candidates(data).values())
            self.assertEqual(output_len, min_len)

    def test_shopsphere_no_data_loss(self):
        """The original bug: all ShopSphere data must survive conversion."""
        output = self._run_pipeline(json.dumps(MIXED_STRUCTURE, indent=2))
        for value in ["ShopSphere", "3.4.2", "production", "electronics",
                       "1203344", "fitness", "842112"]:
            self.assertIn(value, output,
                          f"'{value}' missing from output — data loss!")

    def test_shopsphere_round_trips_via_toon(self):
        """TOON should win for ShopSphere and round-trip perfectly."""
        output = self._run_pipeline(json.dumps(MIXED_STRUCTURE, indent=2))
        # TOON should be the winner here
        recovered = conv.from_toon(output)
        self.assertEqual(normalize(recovered), normalize(MIXED_STRUCTURE))

    def test_list_with_metadata_no_data_loss(self):
        output = self._run_pipeline(json.dumps(LIST_WITH_METADATA, indent=2))
        for val in ["Alpha", "Beta", "Gamma"]:
            self.assertIn(val, output)

    def test_deep_nesting(self):
        output = self._run_pipeline(json.dumps(DEEP_NESTING))
        self.assertIn("deep", output)
        self.assertIn("42", output)

    def test_xml_input(self):
        xml = '<?xml version="1.0"?>\n<cfg><host>example.com</host><port>8080</port></cfg>'
        result = self._run_pipeline(xml)
        self.assertGreater(len(result), 0)
        self.assertIn("example.com", result)
        self.assertIn("8080", result)


# ══════════════════════════════════════════════════════════════════════
#  Tests — Edge Cases: YAML Type Coercion
# ══════════════════════════════════════════════════════════════════════

class TestYamlCoercionSafety(unittest.TestCase):
    """
    YAML is notorious for coercing bare strings into booleans, nulls,
    numbers, or dates. PyYAML's dump() must quote these strings so that
    safe_load() returns them unchanged.
    """

    def _roundtrip(self, data):
        yaml_str = conv.to_yaml_string(data)
        self.assertIsNotNone(yaml_str)
        recovered = conv.from_yaml(yaml_str)
        self.assertEqual(normalize(recovered), normalize(data))

    def test_string_true(self):     self._roundtrip({"val": "true"})
    def test_string_false(self):    self._roundtrip({"val": "false"})
    def test_string_null(self):     self._roundtrip({"val": "null"})
    def test_string_yes(self):      self._roundtrip({"val": "yes"})
    def test_string_no(self):       self._roundtrip({"val": "no"})
    def test_string_on(self):       self._roundtrip({"val": "on"})
    def test_string_off(self):      self._roundtrip({"val": "off"})
    def test_string_True(self):     self._roundtrip({"val": "True"})
    def test_string_NULL(self):     self._roundtrip({"val": "NULL"})
    def test_string_1_0(self):      self._roundtrip({"val": "1.0"})
    def test_string_0(self):        self._roundtrip({"val": "0"})
    def test_string_42(self):       self._roundtrip({"val": "42"})
    def test_string_3_14(self):     self._roundtrip({"val": "3.14"})
    def test_version_string(self):  self._roundtrip({"version": "1.0"})
    def test_date_like_string(self): self._roundtrip({"val": "2024-01-15"})
    def test_time_like_string(self): self._roundtrip({"val": "12:30:00"})
    def test_iso_datetime_string(self): self._roundtrip({"val": "2024-01-15T12:30:00Z"})
    def test_colon_prefix(self):    self._roundtrip({"val": ":colon_start"})
    def test_key_value_string(self): self._roundtrip({"val": "key: value"})

    def test_tabular_with_bool_strings(self):
        """Rows where a string column contains 'true'/'false' literals."""
        data = {"items": [
            {"id": 1, "label": "true",  "val": 10},
            {"id": 2, "label": "false", "val": 20},
        ]}
        self._roundtrip(data)

    def test_tabular_with_null_strings(self):
        data = {"items": [
            {"id": 1, "label": "null", "val": 10},
            {"id": 2, "label": "none", "val": 20},
        ]}
        self._roundtrip(data)


# ══════════════════════════════════════════════════════════════════════
#  Tests — Edge Cases: Empty & Minimal Containers
# ══════════════════════════════════════════════════════════════════════

class TestEmptyContainers(unittest.TestCase):

    def test_empty_object_json(self):
        self.assertEqual(conv.from_json(conv.to_json_compact({})), {})

    def test_empty_object_yaml(self):
        recovered = conv.from_yaml(conv.to_yaml_string({}))
        # PyYAML may return None for empty dict YAML representation
        self.assertIn(recovered, ({}, None))

    def test_empty_object_toon_excluded(self):
        """TOON can't encode {} — it should be excluded from candidates."""
        self.assertIsNone(conv.to_toon_string({}))
        cands = conv.build_candidates({})
        self.assertNotIn("TOON", cands)

    def test_empty_array_json(self):
        self.assertEqual(conv.from_json(conv.to_json_compact([])), [])

    def test_empty_array_yaml(self):
        self.assertEqual(conv.from_yaml(conv.to_yaml_string([])), [])

    def test_object_with_empty_array(self):
        data = {"items": []}
        self.assertEqual(conv.from_json(conv.to_json_compact(data)), data)

    def test_object_with_empty_object(self):
        data = {"nested": {}}
        self.assertEqual(conv.from_json(conv.to_json_compact(data)), data)

    def test_object_with_empty_string(self):
        data = {"val": ""}
        for to_fn, from_fn in [
            (conv.to_json_compact, conv.from_json),
            (conv.to_yaml_string, conv.from_yaml),
            (conv.to_toon_string, conv.from_toon),
        ]:
            encoded = to_fn(data)
            if encoded is not None:
                self.assertEqual(from_fn(encoded), data)


# ══════════════════════════════════════════════════════════════════════
#  Tests — Edge Cases: Null Values
# ══════════════════════════════════════════════════════════════════════

class TestNullValues(unittest.TestCase):

    def _check_all(self, data):
        for to_fn, from_fn, name in [
            (conv.to_json_compact, conv.from_json, "JSON"),
            (conv.to_yaml_string, conv.from_yaml, "YAML"),
            (conv.to_toon_string, conv.from_toon, "TOON"),
        ]:
            encoded = to_fn(data)
            if encoded is not None:
                recovered = from_fn(encoded)
                self.assertEqual(normalize(recovered), normalize(data),
                                 f"{name} null round-trip failed")

    def test_null_in_object(self):
        self._check_all({"a": 1, "b": None, "c": "x"})

    def test_null_in_array(self):
        self._check_all({"arr": [1, None, 3]})

    def test_all_nulls(self):
        self._check_all({"a": None, "b": None})

    def test_top_level_null(self):
        self.assertIsNone(conv.from_json(conv.to_json_compact(None)))


# ══════════════════════════════════════════════════════════════════════
#  Tests — Edge Cases: Special String Content
# ══════════════════════════════════════════════════════════════════════

class TestSpecialStrings(unittest.TestCase):
    """Strings with characters that are delimiters in various formats."""

    def _check_all(self, data):
        for to_fn, from_fn, name in [
            (conv.to_json_compact, conv.from_json, "JSON"),
            (conv.to_yaml_string, conv.from_yaml, "YAML"),
            (conv.to_toon_string, conv.from_toon, "TOON"),
        ]:
            encoded = to_fn(data)
            if encoded is not None:
                recovered = from_fn(encoded)
                self.assertEqual(normalize(recovered), normalize(data),
                                 f"{name} failed for {data}")

    def test_string_with_newline(self):   self._check_all({"val": "line1\nline2"})
    def test_string_with_tab(self):       self._check_all({"val": "col1\tcol2"})
    def test_string_with_comma(self):     self._check_all({"val": "a,b,c"})
    def test_string_with_colon(self):     self._check_all({"val": "key:value"})
    def test_string_with_backslash(self): self._check_all({"val": "path\\to\\file"})
    def test_string_with_double_quotes(self): self._check_all({"val": 'say "hello"'})
    def test_string_with_single_quotes(self): self._check_all({"val": "it's"})
    def test_string_with_brackets(self):  self._check_all({"val": "[not,an,array]"})
    def test_string_with_braces(self):    self._check_all({"val": "{not:an:object}"})
    def test_string_with_hash(self):      self._check_all({"val": "#comment_or_not"})


# ══════════════════════════════════════════════════════════════════════
#  Tests — Edge Cases: Numeric Boundaries
# ══════════════════════════════════════════════════════════════════════

class TestNumericEdgeCases(unittest.TestCase):

    def _check_all(self, data):
        for to_fn, from_fn, name in [
            (conv.to_json_compact, conv.from_json, "JSON"),
            (conv.to_yaml_string, conv.from_yaml, "YAML"),
            (conv.to_toon_string, conv.from_toon, "TOON"),
        ]:
            encoded = to_fn(data)
            if encoded is not None:
                recovered = from_fn(encoded)
                self.assertEqual(normalize(recovered), normalize(data),
                                 f"{name} failed for {data}")

    def test_integer_zero(self):       self._check_all({"val": 0})
    def test_negative_zero(self):      self._check_all({"val": -0.0})
    def test_very_large_int(self):     self._check_all({"val": 99999999999999999})
    def test_very_small_float(self):   self._check_all({"val": 0.000001})
    def test_scientific_notation(self): self._check_all({"val": 1e10})
    def test_negative_float(self):     self._check_all({"val": -3.14})

    def test_top_level_number(self):
        self.assertEqual(conv.from_json(conv.to_json_compact(42)), 42)

    def test_top_level_float(self):
        self.assertAlmostEqual(conv.from_json(conv.to_json_compact(3.14)), 3.14)


# ══════════════════════════════════════════════════════════════════════
#  Tests — Edge Cases: CSV with Tricky Values
# ══════════════════════════════════════════════════════════════════════

class TestCsvEdgeCases(unittest.TestCase):

    def _csv_roundtrip(self, data, expected_rows):
        csv_str = conv.to_csv_string(data)
        self.assertIsNotNone(csv_str)
        recovered = conv.from_csv(csv_str)
        self.assertEqual(recovered, expected_rows)

    def test_values_with_commas(self):
        rows = [{"id": 1, "name": "O'Brien, James", "city": "NY"},
                {"id": 2, "name": "Smith, Jane",    "city": "LA"}]
        self._csv_roundtrip({"items": rows}, rows)

    def test_values_with_newlines(self):
        """Embedded newlines in CSV cells must survive (quoted fields)."""
        rows = [{"id": 1, "note": "line1\nline2"},
                {"id": 2, "note": "single"}]
        self._csv_roundtrip({"items": rows}, rows)

    def test_values_with_commas_and_newlines(self):
        rows = [{"id": 1, "desc": "item A,\nwith comma and newline"},
                {"id": 2, "desc": "simple"}]
        self._csv_roundtrip(rows, rows)

    def test_string_bool_column(self):
        """String column containing 'true'/'false' must stay as strings."""
        rows = [{"id": 1, "label": "true",  "val": 10},
                {"id": 2, "label": "false", "val": 20}]
        csv_str = conv.to_csv_string({"items": rows})
        recovered = conv.from_csv(csv_str)
        self.assertEqual(recovered[0]["label"], "true")
        self.assertIsInstance(recovered[0]["label"], str)

    def test_string_null_column(self):
        """String column containing 'null' must stay as string."""
        rows = [{"id": 1, "label": "null"}]
        csv_str = conv.to_csv_string({"items": rows})
        recovered = conv.from_csv(csv_str)
        self.assertEqual(recovered[0]["label"], "null")
        self.assertIsInstance(recovered[0]["label"], str)

    def test_empty_strings_preserved(self):
        rows = [{"name": "Alice", "note": "", "id": 1},
                {"name": "Bob",   "note": "hi", "id": 2}]
        self._csv_roundtrip(rows, rows)

    def test_double_quotes_in_values(self):
        rows = [{"name": 'O"Brien', "city": "NY", "id": 1}]
        self._csv_roundtrip(rows, rows)

    def test_large_numbers(self):
        rows = [{"big": 9999999999, "small": 0, "neg": -42, "flag": True}]
        self._csv_roundtrip(rows, rows)


# ══════════════════════════════════════════════════════════════════════
#  Tests — Edge Cases: XML Input Shapes
# ══════════════════════════════════════════════════════════════════════

class TestXmlEdgeCases(unittest.TestCase):
    """
    XML inputs parsed via xmltodict produce dicts with special shapes
    (attributes as @keys, CDATA, etc.). Every format must handle them.
    """

    def _pipeline_preserves(self, xml_str, expected_values):
        """Run the pipeline and verify expected values appear in output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            inp = Path(tmpdir) / "input"
            out = Path(tmpdir) / "output"
            inp.write_text(xml_str, encoding="utf-8")
            conv.run(str(inp), str(out))
            output = out.read_text(encoding="utf-8")
            for val in expected_values:
                self.assertIn(val, output, f"'{val}' missing from output")

    def test_xml_with_attributes(self):
        xml = '<?xml version="1.0"?><users><user id="1" name="Alice"/><user id="2" name="Bob"/></users>'
        self._pipeline_preserves(xml, ["Alice", "Bob", "1", "2"])

    def test_xml_with_cdata(self):
        xml = '<?xml version="1.0"?><doc><content><![CDATA[<script>alert("hi")</script>]]></content></doc>'
        data = conv.parse_xml(xml)
        j = conv.to_json_compact(data)
        recovered = conv.from_json(j)
        self.assertIn("alert", str(recovered))

    def test_xml_with_entities(self):
        xml = '<?xml version="1.0"?><doc><val>a &amp; b &lt; c</val></doc>'
        self._pipeline_preserves(xml, ["a & b < c"])

    def test_xml_empty_elements(self):
        xml = '<?xml version="1.0"?><root><empty/><also_empty></also_empty></root>'
        data = conv.parse_xml(xml)
        self.assertIn("root", data)

    def test_xml_multiple_same_children(self):
        """xmltodict collapses multiple same-named children into a list."""
        xml = '<?xml version="1.0"?><root><item>one</item><item>two</item><item>three</item></root>'
        data = conv.parse_xml(xml)
        items = data["root"]["item"]
        self.assertIsInstance(items, list)
        self.assertEqual(len(items), 3)

    def test_xml_single_child_is_string(self):
        """xmltodict keeps a single child as a string, not a list."""
        xml = '<?xml version="1.0"?><root><item>only</item></root>'
        data = conv.parse_xml(xml)
        self.assertEqual(data["root"]["item"], "only")

    def test_xml_with_namespaces(self):
        xml = '<?xml version="1.0"?><root xmlns:ns="http://example.com"><ns:item>test</ns:item></root>'
        data = conv.parse_xml(xml)
        j = conv.to_json_compact(data)
        self.assertIn("test", j)


# ══════════════════════════════════════════════════════════════════════
#  Tests — Edge Cases: TOON-Specific
# ══════════════════════════════════════════════════════════════════════

class TestToonEdgeCases(unittest.TestCase):

    def _toon_roundtrip(self, data):
        encoded = conv.to_toon_string(data)
        self.assertIsNotNone(encoded, f"TOON encode returned None for {data}")
        recovered = conv.from_toon(encoded)
        self.assertEqual(normalize(recovered), normalize(data))

    def test_unicode_emoji(self):
        self._toon_roundtrip({"msg": "Hej världen 🌍", "count": 1})

    def test_empty_string_value(self):
        self._toon_roundtrip({"val": ""})

    def test_nested_arrays(self):
        self._toon_roundtrip({"matrix": [[1, 2], [3, 4]]})

    def test_mixed_type_array(self):
        self._toon_roundtrip({"vals": [1, "two", True, None, 3.14]})

    def test_string_with_toon_delimiters(self):
        """Strings containing commas and colons must be quoted in TOON."""
        self._toon_roundtrip({"val": "a,b,c"})
        self._toon_roundtrip({"val": "key: value"})
        self._toon_roundtrip({"val": "line1\nline2"})

    def test_empty_object_excluded(self):
        self.assertIsNone(conv.to_toon_string({}))

    def test_empty_array(self):
        self._toon_roundtrip({"items": []})

    def test_null_value(self):
        self._toon_roundtrip({"val": None})

    def test_tabular_with_comma_values(self):
        """Tabular rows where values contain commas (TOON's row delimiter)."""
        data = {"items": [
            {"id": 1, "name": "O'Brien, James"},
            {"id": 2, "name": "Smith, Jane"},
        ]}
        self._toon_roundtrip(data)

    def test_tabular_with_colon_values(self):
        data = {"items": [
            {"id": 1, "note": "time: 12:00"},
            {"id": 2, "note": "time: 13:00"},
        ]}
        self._toon_roundtrip(data)


# ══════════════════════════════════════════════════════════════════════
#  Tests — Edge Cases: Top-Level Primitives
# ══════════════════════════════════════════════════════════════════════

class TestTopLevelPrimitives(unittest.TestCase):
    """JSON allows top-level primitives. The pipeline must handle them."""

    def test_top_level_string(self):
        data = "hello world"
        self.assertEqual(conv.from_json(conv.to_json_compact(data)), data)

    def test_top_level_true(self):
        self.assertEqual(conv.from_json(conv.to_json_compact(True)), True)

    def test_top_level_false(self):
        self.assertEqual(conv.from_json(conv.to_json_compact(False)), False)

    def test_top_level_null(self):
        self.assertIsNone(conv.from_json(conv.to_json_compact(None)))

    def test_top_level_int(self):
        self.assertEqual(conv.from_json(conv.to_json_compact(42)), 42)

    def test_top_level_float(self):
        self.assertAlmostEqual(conv.from_json(conv.to_json_compact(3.14)), 3.14)

    def test_pipeline_top_level_string(self):
        """Full pipeline with a bare JSON string input."""
        with tempfile.TemporaryDirectory() as tmpdir:
            inp = Path(tmpdir) / "input"
            out = Path(tmpdir) / "output"
            inp.write_text('"hello world"', encoding="utf-8")
            conv.run(str(inp), str(out))
            self.assertTrue(out.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)