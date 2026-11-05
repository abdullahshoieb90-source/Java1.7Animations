#!/usr/bin/env python3
"""
Self-tests for tools/brarchive.py and tools/vanilla_index.py.

Run with:  python3 tools/test_brarchive.py

The fixtures are built byte by byte from the layout documented in
`brarchive.py`, so a change in the reader that only works for one specific dump
will show up here.
"""

import json
import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import brarchive  # noqa: E402

MAGIC = b"\x7d\x27\x25\xb1"
RECORD = 256
COMPILED = b"\x7f\x4d\x43\x42"


def build_archive(names, payload, compiled=False, opaque_ids=None):
    """
    Assemble an archive. `payload` is the raw payload region: for JSON archives
    pass the exact bytes, for compiled archives anything starting with the marker.
    """
    header = bytearray()
    for index, name in enumerate(names):
        raw = name.encode()
        record = bytearray(RECORD)
        opaque = (opaque_ids or {}).get(index, index + 1)
        struct.pack_into("<I", record, 0, opaque)
        record[4] = len(raw)
        record[5 : 5 + len(raw)] = raw
        header += record
    if compiled:
        payload = COMPILED + payload
    return MAGIC + struct.pack("<II", 0x1234ABCD, len(names)) + bytes(header) + payload


def write_archive(directory, name, *args, **kwargs):
    path = os.path.join(directory, name)
    with open(path, "wb") as fh:
        fh.write(build_archive(*args, **kwargs))
    return path


class BrarchiveTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_reads_json_entries_in_order(self):
        docs = [
            {"format_version": "1.26.0", "minecraft:entity": {"description": {"identifier": "minecraft:a"}}},
            {"format_version": "1.26.0", "minecraft:entity": {"description": {"identifier": "minecraft:b"}}},
        ]
        # Bedrock separates documents with a few non-JSON bytes; reproduce that.
        payload = b"\x01\x00\x00\x00" + json.dumps(docs[0]).encode()
        payload += b"}}}\x00\x00" + json.dumps(docs[1]).encode()
        path = write_archive(self.dir, "entities.brarchive", ["a.json", "b.json"], payload)

        archive = brarchive.read_archive(path)
        self.assertEqual(archive["count"], 2)
        self.assertEqual(archive["encoding"], "json")
        self.assertTrue(archive["complete"])
        self.assertEqual(archive["names"], ["a.json", "b.json"])
        identifiers = [d["minecraft:entity"]["description"]["identifier"] for d in archive["documents"]]
        self.assertEqual(identifiers, ["minecraft:a", "minecraft:b"])

    def test_header_fields(self):
        path = write_archive(self.dir, "x.brarchive", ["one.json"], b"{}")
        archive = brarchive.read_archive(path)
        self.assertEqual(archive["size"], os.path.getsize(path))
        self.assertRegex(archive["hash"], r"^[0-9a-f]{8}$")

    def test_opaque_id_is_not_used_as_length(self):
        # A real archive reports 1 for a record whose payload is a whole document.
        path = write_archive(
            self.dir, "x.brarchive", ["agent.json"], b'{"a":1}', opaque_ids={0: 1}
        )
        archive = brarchive.read_archive(path)
        self.assertTrue(archive["complete"])
        self.assertEqual(archive["documents"], [{"a": 1}])

    def test_compiled_marker_is_detected(self):
        path = write_archive(self.dir, "shapes.brarchive", ["anvil.json"], b"\x01\x15\x00", compiled=True)
        archive = brarchive.read_archive(path)
        self.assertEqual(archive["encoding"], "compiled")
        self.assertEqual(archive["names"], ["anvil.json"])
        self.assertEqual(archive["documents"], [])

    def test_empty_archive_is_not_an_error(self):
        path = write_archive(self.dir, "poi.brarchive", [], b"")
        archive = brarchive.read_archive(path)
        self.assertEqual(archive["encoding"], "empty")
        self.assertTrue(archive["complete"])
        self.assertEqual(archive["count"], 0)

    def test_partial_json_is_reported_as_incomplete(self):
        path = write_archive(self.dir, "trading.brarchive", ["a.json", "b.json"], b'{"tiers": []}')
        archive = brarchive.read_archive(path)
        self.assertEqual(archive["encoding"], "json")
        self.assertFalse(archive["complete"])
        self.assertEqual(len(archive["documents"]), 1)

    def test_bad_magic_raises(self):
        path = os.path.join(self.dir, "bad.brarchive")
        with open(path, "wb") as fh:
            fh.write(b"NOTABRCHIVE" + bytes(64))
        with self.assertRaises(brarchive.BrarchiveError):
            brarchive.read_archive(path)

    def test_truncated_header_raises(self):
        path = os.path.join(self.dir, "short.brarchive")
        with open(path, "wb") as fh:
            fh.write(MAGIC + struct.pack("<II", 0, 500))
        with self.assertRaises(brarchive.BrarchiveError):
            brarchive.read_archive(path)

    def test_entries_helper_pairs_names_with_documents(self):
        payload = json.dumps({"k": 1}).encode()
        path = write_archive(self.dir, "x.brarchive", ["a.json"], payload)
        self.assertEqual(list(brarchive.entries(path)), [("a.json", {"k": 1})])

    def test_cli_get_and_dump(self):
        payload = json.dumps({"k": 2}).encode()
        path = write_archive(self.dir, "x.brarchive", ["a.json"], payload)
        out_dir = os.path.join(self.dir, "out")
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(brarchive.main(["get", path, "a.json"]), 0)
        self.assertEqual(json.loads(buf.getvalue()), {"k": 2})
        self.assertEqual(brarchive.main(["dump", path, out_dir]), 0)
        with open(os.path.join(out_dir, "a.json")) as fh:
            self.assertEqual(json.load(fh), {"k": 2})


if __name__ == "__main__":
    unittest.main(verbosity=2)
