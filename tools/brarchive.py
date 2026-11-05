#!/usr/bin/env python3
"""
Reader for Bedrock's `__brarchive` container format.

From ~1.21 onwards Bedrock no longer ships the vanilla behaviour pack as loose
JSON. Instead each content folder (entities, recipes, biomes, trading, ...) is
one `.brarchive` blob inside `<pack>/__brarchive/`. This module opens them so the
data can be inspected, diffed and indexed — useful when porting behaviour from
one game version to another.

Layout (little endian), verified against a real 1.26 vanilla behaviour pack dump
(69 pack folders, 303 archives, every JSON archive recovered with an exact
entry count):

    offset 0    u32  magic           0xB125277D  (bytes 7d 27 25 b1)
    offset 4    u32  content hash    stable per archive, purpose undocumented
    offset 8    u32  count           number of entries
    offset 12   count x 256-byte records:
                    u32  opaque id (not a length — see note below)
                    u8   nlen      length of the entry name
                    u8*  name      e.g. "agent.json"
                    ..   zero padding up to 256 bytes
    then        the payload region.

Two payload encodings exist, and the encoding is a property of the whole
archive, not of a single entry:

  * **json** - the region is the concatenation of one JSON document per record,
    in record order. Documents are separated by a few non-JSON bytes whose
    meaning is undocumented, so the reader scans for the next `{`/`[` and uses
    `json.JSONDecoder.raw_decode`, which consumes exactly one document and
    reports where it ended. This recovers all 264 JSON archives in the dump
    with counts matching the header.

  * **compiled** - the region contains the marker ``7f 4d 43 42`` and holds a
    binary, chunked encoding. In a 1.26 dump this is only used for
    `item_catalog` (26 archives), `items` (3) and `shapes` (1). The schema is not
    public, so those archives are reported as `compiled` and only their entry
    *names* are exposed.

  * **empty** - the header declares `count == 0`; the two ``server_*_library``
    packs ship these. Not an error.

Note on the per-record `u32`: it looks like a length but it is not. In
`entities.brarchive` the first record reports `1` while its payload is a whole
entity JSON document. Treat it as an opaque id.

CLI
---
    python3 tools/brarchive.py info <file.brarchive>
    python3 tools/brarchive.py list <file.brarchive>
    python3 tools/brarchive.py get  <file.brarchive> <entry-name>
    python3 tools/brarchive.py dump <file.brarchive> <output-dir>
"""

from __future__ import annotations

import argparse
import json
import os
import struct
import sys

MAGIC = b"\x7d\x27\x25\xb1"
RECORD_SIZE = 256
COMPILED_MARKER = b"\x7f\x4d\x43\x42"
JSON_STARTS = ("{", "[")


class BrarchiveError(Exception):
    pass


def _read_header(data: bytes):
    if len(data) < 12:
        raise BrarchiveError("file is shorter than the 12 byte header")
    if data[:4] != MAGIC:
        raise BrarchiveError(
            f"not a brarchive (expected magic {MAGIC.hex()}, got {data[:4].hex()})"
        )
    count = struct.unpack("<I", data[8:12])[0]
    header_end = 12 + count * RECORD_SIZE
    if header_end > len(data):
        raise BrarchiveError(f"header declares {count} entries but the file is too small")
    names = []
    for index in range(count):
        base = 12 + index * RECORD_SIZE
        name_length = data[base + 4]
        names.append(data[base + 5 : base + 5 + name_length].decode("utf-8", "replace"))
    return count, header_end, names


def _scan_json(text: str):
    """Yield raw JSON documents from a payload region, skipping separator bytes."""
    decoder = json.JSONDecoder()
    index, length = 0, len(text)
    while index < length:
        while index < length and text[index] not in JSON_STARTS:
            index += 1
        if index >= length:
            return
        try:
            document, end = decoder.raw_decode(text, index)
        except ValueError:
            return
        yield document
        index = end


def read_archive(path: str):
    """
    Return a dict describing the archive:

        {
          "path": ..., "size": ..., "hash": ..., "count": ...,
          "encoding": "json" | "compiled",
          "names": [entry names in header order],
          "documents": [parsed JSON docs] or [] when compiled,
          "complete": bool  # documents cover every header entry
        }
    """
    with open(path, "rb") as fh:
        data = fh.read()
    count, header_end, names = _read_header(data)
    payload = data[header_end:]

    result = {
        "path": path,
        "size": len(data),
        "hash": "%08x" % struct.unpack("<I", data[4:8])[0],
        "count": count,
        "names": names,
        "encoding": "json",
        "documents": [],
        "complete": False,
    }

    if count == 0:
        result["encoding"] = "empty"
        result["complete"] = True
        return result

    if COMPILED_MARKER in payload[:128]:
        result["encoding"] = "compiled"
        return result

    documents = list(_scan_json(payload.decode("utf-8", "surrogateescape")))
    result["documents"] = documents
    result["complete"] = len(documents) == count
    if not documents:
        result["encoding"] = "unknown"
    return result


def entries(path: str):
    """Yield (name, document_or_None) pairs, in header order."""
    archive = read_archive(path)
    for index, name in enumerate(archive["names"]):
        document = archive["documents"][index] if index < len(archive["documents"]) else None
        yield name, document


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read Bedrock __brarchive containers.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("info", "summarise an archive (encoding, hash, entry names)"),
        ("list", "print entry names"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("archive")
    p_get = sub.add_parser("get", help="print a single entry as JSON")
    p_get.add_argument("archive")
    p_get.add_argument("entry")
    p_dump = sub.add_parser("dump", help="extract every JSON entry to a directory")
    p_dump.add_argument("archive")
    p_dump.add_argument("output_dir")

    args = parser.parse_args(argv)

    try:
        if args.command == "info":
            archive = read_archive(args.archive)
            summary = {k: v for k, v in archive.items() if k not in ("names", "documents")}
            summary["first_entries"] = archive["names"][:10]
            summary["documents_parsed"] = len(archive["documents"])
            print(json.dumps(summary, indent=2))
        elif args.command == "list":
            archive = read_archive(args.archive)
            for name in archive["names"]:
                print(name)
        elif args.command == "get":
            for name, document in entries(args.archive):
                if name == args.entry:
                    if document is None:
                        print(
                            f"{name}: archive uses the compiled encoding, no JSON available",
                            file=sys.stderr,
                        )
                        return 2
                    print(json.dumps(document, indent=2, ensure_ascii=False))
                    return 0
            print(f"entry {args.entry!r} not found", file=sys.stderr)
            return 1
        elif args.command == "dump":
            archive = read_archive(args.archive)
            if archive["encoding"] == "compiled":
                print(
                    f"{args.archive}: compiled encoding, only entry names are available",
                    file=sys.stderr,
                )
                return 2
            os.makedirs(args.output_dir, exist_ok=True)
            written = 0
            for index, name in enumerate(archive["names"]):
                if index >= len(archive["documents"]):
                    break
                target = os.path.join(args.output_dir, name)
                os.makedirs(os.path.dirname(target) or args.output_dir, exist_ok=True)
                with open(target, "w", encoding="utf-8") as fh:
                    json.dump(archive["documents"][index], fh, indent=2, ensure_ascii=False)
                    fh.write("\n")
                written += 1
            print(f"wrote {written} entries to {args.output_dir}")
    except BrarchiveError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
