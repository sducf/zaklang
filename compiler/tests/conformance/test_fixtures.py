"""Check SD-35 fixture structure and syntax independently of compiler semantics.

These checks do not compile, transpile, or execute Zak programs.
"""

import json
from pathlib import Path

import pytest
from lark import Lark


ROOT = Path(__file__).resolve().parents[3]
CORPUS = Path(__file__).resolve().parent
TASKS = ROOT / "zakbench" / "tasks"
TASK_IDS = ("array_sum", "palindrome", "frequency_count")


@pytest.fixture(scope="module")
def parser():
    return Lark(
        (ROOT / "compiler" / "src" / "grammar.txt").read_text(encoding="utf-8"),
        parser="lalr",
        start="start",
    )


def test_corpus_has_fifteen_programs_and_matching_outputs():
    programs = {path.stem for path in CORPUS.glob("*.zak")}
    outputs = {path.stem for path in CORPUS.glob("*.expected")}
    assert len(programs) == 15
    assert outputs == programs


@pytest.mark.parametrize("path", sorted(CORPUS.glob("*.zak")), ids=lambda p: p.stem)
def test_conformance_program_parses(parser, path):
    parser.parse(path.read_text(encoding="utf-8"))
    expected = path.with_suffix(".expected").read_bytes()
    assert expected.endswith(b"\n"), "out(x) includes a trailing newline"


def test_corpus_covers_sd1_constructs(parser):
    rules = set()
    for path in CORPUS.glob("*.zak"):
        tree = parser.parse(path.read_text(encoding="utf-8"))
        rules.update(str(node.data) for node in tree.iter_subtrees())
    # Pin all construct families represented by the 15-program coverage table.
    # Comprehensions are outside the statically supported SD1 subset.
    assert {
        "decl", "assign", "binop", "neg", "float_lit", "compare",
        "true", "false", "and_op", "or_op", "not_op", "if_",
        "while_", "for_", "fn", "param", "ret", "call", "brk", "cont",
        "arr", "arr_t", "push", "index", "length", "str_lit", "slice",
        "map", "map_t", "member",
    } <= rules


@pytest.mark.parametrize("task_id", TASK_IDS)
def test_reference_signature_matches_task(parser, task_id):
    folder = TASKS / task_id
    task = json.loads((folder / "task.json").read_text(encoding="utf-8"))
    tree = parser.parse((folder / "reference.zak").read_text(encoding="utf-8"))
    functions = list(tree.find_data("fn"))
    assert len(functions) == 1
    function = functions[0]
    assert str(function.children[0]) == task["functionName"]
    params = list(function.find_data("param"))
    assert [str(param.children[0]) for param in params] == [item["name"] for item in task["inputs"]]
