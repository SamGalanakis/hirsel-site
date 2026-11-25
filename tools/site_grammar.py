#!/usr/bin/env python3
"""Load the Hirsel Tree-sitter grammar (editors/tree-sitter-hirsel in the Hirsel checkout) and
turn source lines into per-line highlight ranges.

Needs a C compiler and py-tree-sitter 0.25.2 (`pip install tree-sitter==0.25.2`). When
tree_sitter is not importable, the caller re-runs itself under the interpreter that the Hirsel
checkout's editors/tree-sitter-hirsel/check-local installs, if one is present.
"""

import ctypes
import os
import subprocess
import sys
from pathlib import Path

from site_paths import HIRSEL

GRAMMAR = HIRSEL / "editors" / "tree-sitter-hirsel"


def ensure_binding(script_path: str) -> None:
    try:
        import tree_sitter  # noqa: F401
    except ImportError:
        python = (
            Path.home()
            / ".cache"
            / "hirsel-tree-sitter"
            / f"binding-0.25.2-{sys.implementation.cache_tag}"
            / "bin"
            / "python"
        )
        if not python.is_file() or os.environ.get("SITE_HIGHLIGHT_REEXEC"):
            sys.exit(
                "site_grammar: py-tree-sitter 0.25.2 missing; "
                "pip install tree-sitter==0.25.2"
            )
        os.execve(
            python,
            [str(python), script_path, *sys.argv[1:]],
            dict(os.environ, SITE_HIGHLIGHT_REEXEC="1"),
        )


def load_grammar(temp_dir: str):
    from tree_sitter import Language, Parser, Query

    lib = Path(temp_dir) / "hirsel.so"
    subprocess.run(
        [
            "cc",
            "-shared",
            "-fPIC",
            "-O1",
            "-I",
            str(GRAMMAR / "src"),
            str(GRAMMAR / "src" / "parser.c"),
            str(GRAMMAR / "src" / "scanner.c"),
            "-o",
            str(lib),
        ],
        check=True,
    )
    grammar = ctypes.CDLL(str(lib))
    entry = grammar.tree_sitter_hirsel
    entry.restype = ctypes.c_void_p
    capsule = ctypes.pythonapi.PyCapsule_New
    capsule.argtypes = (ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p)
    capsule.restype = ctypes.py_object
    language = Language(capsule(entry(), b"tree_sitter.Language", None))
    parser = Parser(language)
    query = Query(language, (GRAMMAR / "queries" / "highlights.scm").read_text())
    return grammar, parser, query


def tokenize_lines(
    parser,
    query,
    lines: list[str],
    class_map: dict[str, str],
    label: str = "snippet",
) -> list[list[list]]:
    from tree_sitter import QueryCursor

    errors = []
    for line in lines:
        if not line.isascii():
            errors.append(f"{label}: non-ASCII line {line!r}")
    source = "\n".join(lines).encode()
    tree = parser.parse(source)
    if tree.root_node.has_error:
        errors.append(f"{label}: parse error\n{tree.root_node}")
    if errors:
        raise ValueError("\n".join(errors))

    # One class per node: earliest pattern in queries/highlights.scm wins.
    chosen: dict[tuple[int, int], tuple[int, str]] = {}
    for pattern, caps in QueryCursor(query).matches(tree.root_node):
        for capture, nodes in caps.items():
            for node in nodes:
                key = (node.start_byte, node.end_byte)
                if key not in chosen or pattern < chosen[key][0]:
                    chosen[key] = (pattern, capture)

    starts = [0]
    for line in lines:
        starts.append(starts[-1] + len(line) + 1)

    # One class per byte: earliest pattern in queries/highlights.scm wins, including when
    # an outer node such as (attribute) contains inner punctuation or type captures.
    ranges: list[list[list]] = [[] for _ in lines]
    accepted: list[tuple[int, int]] = []
    for (start_b, end_b), (_, capture) in sorted(
        chosen.items(), key=lambda item: (item[1][0], item[0][0], -(item[0][1] - item[0][0]))
    ):
        cls = class_map.get(capture)
        if not cls:
            continue
        if any(start_b < a_end and end_b > a_start for a_start, a_end in accepted):
            continue
        row = max(i for i, s in enumerate(starts) if s <= start_b)
        if end_b > starts[row] + len(lines[row]):
            errors.append(f"{label}: capture {capture} spans lines")
            continue
        accepted.append((start_b, end_b))
        ranges[row].append([start_b - starts[row], end_b - start_b, cls])

    for row in ranges:
        row.sort(key=lambda item: item[0])
        for prev, cur in zip(row, row[1:]):
            if cur[0] < prev[0] + prev[1]:
                errors.append(f"{label}: overlapping ranges {prev} {cur}")
    if errors:
        raise ValueError("\n".join(errors))
    return ranges
