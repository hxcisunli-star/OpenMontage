import builtins
import importlib.util
import json
from pathlib import Path
import random
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "lab_runner", ROOT / "docs/whiteboard/ebook/lab-runner.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def run(code, *, mode="run", prelude="", tests=(), seed=None):
    return runner.run_request(mode, code, prelude, tests, seed)


def check(code, test_code, **kwargs):
    return run(code, mode="check", tests=[
        {"id": "sample", "name": "示例检查", "code": test_code}], **kwargs)


def payload(text):
    assert text.endswith("……输出太长，已截断\n")
    return text.removesuffix("……输出太长，已截断\n")


def test_result_shape_and_standard_types():
    result = run("print('你好')")
    assert set(result) == {"ok", "stdout", "stderr", "truncated", "durationMs", "error", "checks"}
    assert result["ok"] is True
    assert result["stdout"] == "你好\n"
    assert result["stderr"] == ""
    assert result["truncated"] is False
    assert result["checks"] == []
    assert result["error"] is None
    assert isinstance(result["durationMs"], (float, int))
    assert result["durationMs"] >= 0
    assert json.loads(json.dumps(result)) == result


@pytest.mark.parametrize("bad_code,kind", [
    ("print（'你好'）", "SyntaxError"),
    ("if True\n    pass", "SyntaxError"),
    ("  x = 1", "IndentationError"),
    ("if True:\npass", "IndentationError"),
    ("print(1", "SyntaxError"),
])
def test_syntax_errors_execute_neither_student_nor_prelude(monkeypatch, bad_code, kind):
    calls = []
    monkeypatch.setattr(builtins, "_lab_probe", lambda: calls.append(True), raising=False)
    result = run("_lab_probe()\n" + bad_code, prelude="_lab_probe()")
    assert result["ok"] is False
    assert result["stdout"] == ""
    assert result["error"]["type"] == kind
    assert result["error"]["lineno"] >= 2
    assert result["error"]["colno"] >= 1
    assert calls == []
    assert result["checks"] == []


@pytest.mark.parametrize("character,replacement", list(runner._PUNCTUATION.items()))
def test_fullwidth_punctuation_points_to_exact_character(character, replacement):
    result = run("x = 1\nprint" + character + "1")
    error = result["error"]
    assert error["type"] == "SyntaxError"
    assert error["lineno"] == 2
    assert error["colno"] == 6
    assert "第 2 行第 6 列" in error["hintZh"]
    assert "“" + character + "”" in error["hintZh"]
    assert "半角“" + replacement + "”" in error["hintZh"]
    assert len(error["hintZh"]) <= 60


@pytest.mark.parametrize("source,kind,words", [
    ("print(missing)", "NameError", "先给变量赋值"),
    ("print(___)", "NameError", "没填的空白"),
    ("def f():\n print(x)\n x = 1\nf()", "UnboundLocalError", "先给变量赋值"),
    ("1 + 'a'", "TypeError", "类型"),
    ("1 / 0", "ZeroDivisionError", "除数不能是 0"),
    ("[][0]", "IndexError", "序号从 0 开始"),
    ("{}['missing']", "KeyError", "键"),
    ("int('猫')", "ValueError", "整数"),
    ("import nonexisting_lab_module", "ModuleNotFoundError", "这个练习只能用 Python 自带的库"),
    ("(1).missing", "AttributeError", "属性或方法"),
    ("def f():\n f()\nf()", "RecursionError", "结束递归"),
    ("print(1", "SyntaxError", "括号没有配对"),
    ("x = [1)", "SyntaxError", "括号没有配对"),
    ("x = ]", "SyntaxError", "括号没有配对"),
    ("if True:\nprint(1)", "IndentationError", "下一行向右缩进 4 个空格"),
    ("  print(1)", "IndentationError", "多缩进"),
    ("if True:\n    x = 1\n  y = 2", "IndentationError", "缩进没有对齐"),
    ("if True:\n\tx = 1\n        y = 2", "TabError", "统一用空格"),
    ("if True\n    pass", "SyntaxError", "语法"),
    ("raise RuntimeError('失败')", "RuntimeError", "错误消息"),
    ("input('名字？')", "RuntimeError", "请直接把值写进变量"),
])
def test_hints_are_short_and_actionable(source, kind, words):
    result = run(source)
    assert result["ok"] is False
    assert result["error"]["type"] == kind
    assert words in result["error"]["hintZh"]
    assert 0 < len(result["error"]["hintZh"]) <= 60


def test_fullwidth_text_in_strings_does_not_mask_a_runtime_hint():
    result = run("label = '（）'\n1 + 'a'")
    assert "类型" in result["error"]["hintZh"]


def test_runtime_traceback_keeps_only_student_frames_and_inner_line():
    result = run("import json\ndef parse():\n    return json.loads('oops')\nparse()")
    error = result["error"]
    assert error["type"] == "JSONDecodeError"
    assert error["lineno"] == 3
    assert error["colno"] is None
    text = error["traceback"]
    assert text.startswith("Traceback (most recent call last):\n")
    assert 'File "<练习>", line 4, in <module>' in text
    assert 'File "<练习>", line 3, in parse' in text
    assert "return json.loads('oops')" in text
    assert text.count('File "') == 2
    assert "lab-runner" not in text
    assert "decoder.py" not in text
    assert "JSONDecodeError:" in text


def test_prelude_function_frame_is_not_shown_as_student_code():
    result = run("helper()", prelude="def helper():\n    return 1 / 0")
    assert result["error"]["lineno"] == 1
    assert result["error"]["traceback"].count('File "') == 1
    assert "<练习准备>" not in result["error"]["traceback"]


@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_line_limit_and_stream_independence(stream):
    other = "stderr" if stream == "stdout" else "stdout"
    result = run(f"import sys\nsys.{stream}.write('行\\n' * 250)\nsys.{other}.write('另一条\\n')")
    assert result["ok"] is True
    assert result["truncated"] is True
    assert payload(result[stream]) == "行\n" * 200
    assert result[other] == "另一条\n"


@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_character_limit_counts_unicode_characters(stream):
    result = run(f"import sys\nsys.{stream}.write('猫' * 20000)")
    assert result["truncated"] is True
    assert payload(result[stream]) == "猫" * 16384 + "\n"


@pytest.mark.parametrize("text", ["a\n" * 200, "猫" * 16384, "a\n" * 199 + "a"])
def test_exact_limit_is_not_truncated(text):
    result = run(f"import sys\nsys.stdout.write({text!r})\nsys.stdout.write('')")
    assert result["stdout"] == text
    assert result["truncated"] is False


def test_limit_is_shared_across_multiple_writes_and_first_limit_wins():
    result = run("import sys\nfor i in range(500):\n sys.stdout.write('x' * 99 + '\\n')")
    assert result["truncated"] is True
    text = payload(result["stdout"])
    assert text == ("x" * 99 + "\n") * 163 + "x" * 84 + "\n"
    assert len(text.removesuffix("\n")) == 16384


def test_line_200_can_be_finished_by_a_later_write():
    result = run("import sys\nsys.stdout.write('a\\n' * 199 + 'last')\nsys.stdout.write(' line\\n')\nsys.stdout.write('discard')")
    assert payload(result["stdout"]) == "a\n" * 199 + "last line\n"


def test_truncation_survives_runtime_error_and_is_visible_to_checks():
    result = run("print('x' * 17000)\n1/0")
    assert result["truncated"] is True
    assert "已截断" in result["stdout"]
    assert result["error"]["type"] == "ZeroDivisionError"
    assert check("print('x' * 17000)", "assert STDOUT.endswith('……输出太长，已截断\\n')")["ok"] is True


def test_fresh_globals_and_builtins_for_each_request():
    assert run("x = 12\n__builtins__['lab_only'] = 1")["ok"] is True
    result = check("assert __name__ == '__main__'", "assert 'x' not in NS\nassert 'lab_only' not in NS['__builtins__']")
    assert result["ok"] is True
    assert run("print(x)")["error"]["type"] == "NameError"


@pytest.mark.parametrize("code,prelude", [
    ("import random\nrandom.seed(99)\nprint(random.random())", ""),
    ("import random\nprint(random.random())", "import random\nrandom.seed(77)"),
    ("import random\nrandom.random()\n1/0", ""),
    ("pass", "import random\nrandom.random()\n1/0"),
])
def test_random_state_is_restored_even_on_failure(code, prelude):
    before = random.getstate()
    run(code, prelude=prelude, seed=1)
    assert random.getstate() == before


def test_two_unseeded_requests_cannot_pollute_each_others_random_state():
    code = "import random\nprint(random.random())"
    baseline = run(code)["stdout"]
    run("import random\nrandom.seed(999)\nrandom.random()")
    assert run(code)["stdout"] == baseline


def test_seed_is_applied_after_prelude_and_is_repeatable():
    code = "print(random.random())"
    prelude = "import random\nrandom.seed(912)\nrandom.random()"
    expected = str(random.Random(5).random()) + "\n"
    assert run(code, prelude=prelude, seed=5)["stdout"] == expected
    assert run(code, prelude=prelude, seed=5)["stdout"] == expected
    assert run(code, prelude=prelude, seed=6)["stdout"] != expected


def test_prelude_shares_namespace_but_its_output_is_discarded():
    result = run("print(x + 1)", prelude="import sys\nx = 41\nprint('a' * 20000)\nsys.stderr.write('b' * 20000)")
    assert result["ok"] is True
    assert result["stdout"] == "42\n"
    assert result["stderr"] == ""
    assert result["truncated"] is False


@pytest.mark.parametrize("prelude", ["1/0", "if True", "raise SystemExit(1)"])
def test_prelude_failure_is_internal_and_skips_student_and_checks(prelude):
    result = check("print('student')", "assert False", prelude=prelude)
    assert result["ok"] is False
    assert result["error"]["type"] == "PreludeError"
    assert result["error"]["lineno"] is None
    assert "课程作者" in result["error"]["hintZh"]
    assert result["stdout"] == ""
    assert result["checks"] == []


@pytest.mark.parametrize("code", ["input()", "import builtins\nbuiltins.input('prompt')"])
def test_input_is_disabled_and_host_input_is_restored(code):
    original = builtins.input
    result = run(code)
    assert result["error"]["type"] == "RuntimeError"
    assert result["error"]["message"] == runner._INPUT_ERROR
    assert result["stdout"] == ""
    assert builtins.input is original


def test_check_names_messages_fresh_dictionaries_and_stdout_isolation():
    tests = [
        {"id": "pass", "name": "通过", "code": "assert USER_CODE == 'x = 3\\nprint(x)'\nassert STDOUT == '3\\n'\nassert NS['x'] == 3\nprivate = 1\nprint('ignored')"},
        {"id": "assert", "name": "断言", "code": "assert False, '请输出三行'"},
        {"id": "empty", "name": "空消息", "code": "assert False"},
        {"id": "error", "name": "检查错误", "code": "raise ValueError('bad')"},
        {"id": "fresh", "name": "新环境", "code": "assert 'private' not in globals()"},
    ]
    result = run("x = 3\nprint(x)", mode="check", tests=tests)
    assert result["ok"] is False
    assert result["error"] is None
    assert result["stdout"] == "3\n"
    assert result["checks"] == [
        {"id": "pass", "name": "通过", "passed": True, "message": ""},
        {"id": "assert", "name": "断言", "passed": False, "message": "请输出三行"},
        {"id": "empty", "name": "空消息", "passed": False, "message": ""},
        {"id": "error", "name": "检查错误", "passed": False, "message": "检查代码出错：ValueError: bad"},
        {"id": "fresh", "name": "新环境", "passed": True, "message": ""},
    ]


def test_run_with_seed_repeats_prelude_in_fresh_namespace_and_preserves_parent_random():
    code = "import random\nvalues.append(random.randrange(1000000))\nprint(values)"
    prelude = "values = []\nprint('discarded')\nimport random\nrandom.random()"
    test_code = """
import random
state = random.getstate()
a = RUN_WITH_SEED(1)
b = RUN_WITH_SEED(2)
assert a == RUN_WITH_SEED(1)
assert a != b
assert a.count(',') == 0
assert 'discarded' not in a
assert random.getstate() == state
assert len(NS['values']) == 1
"""
    result = check(code, test_code, prelude=prelude, seed=1)
    assert result["ok"] is True


def test_run_with_seed_propagates_same_exception_and_does_not_break_other_checks():
    code = "import random\nif random.random() < 0.5:\n raise ValueError('same')\nprint('ok')"
    assert run(code, seed=2)["ok"] is True
    result = check(code, """
try:
    RUN_WITH_SEED(1)
except ValueError as error:
    assert str(error) == 'same'
else:
    assert False, '没有传播异常'
assert RUN_WITH_SEED(2) == STDOUT
""", seed=2)
    assert result["ok"] is True
    result = check(code, "RUN_WITH_SEED(1)", seed=2)
    assert result["checks"][0]["message"] == "检查代码出错：ValueError: same"


def test_run_with_seed_also_limits_output_and_disables_input():
    assert check("print('x' * 20000)", "assert RUN_WITH_SEED(1) == STDOUT")["ok"] is True
    code = "import random\nif random.random() < .5: input()"
    result = check(code, "RUN_WITH_SEED(1)", seed=2)
    assert runner._INPUT_ERROR in result["checks"][0]["message"]


def test_student_failure_never_runs_checks(monkeypatch):
    calls = []
    monkeypatch.setattr(builtins, "_lab_probe", lambda: calls.append(True), raising=False)
    result = check("1/0", "_lab_probe()")
    assert result["checks"] == []
    assert result["ok"] is False
    assert calls == []


def test_run_mode_never_runs_checks_and_check_mode_requires_all_pass():
    assert run("pass", tests=[{"code": "raise AssertionError"}])["ok"] is True
    assert run("pass")["checks"] == []
    assert check("pass", "assert True")["ok"] is True
    assert check("pass", "assert False")["ok"] is False
    assert check("1/0", "assert True")["ok"] is False


@pytest.mark.parametrize("exception", ["SystemExit", "KeyboardInterrupt", "GeneratorExit"])
def test_base_exceptions_become_results(exception):
    result = run(f"raise {exception}('stop')")
    assert result["ok"] is False
    assert result["error"]["type"] == exception
    result = check("pass", f"raise {exception}('stop')")
    assert result["checks"][0]["message"] == f"检查代码出错：{exception}: stop"


def test_sleep_is_not_replaced_and_recursion_limit_is_unchanged():
    limit = sys.getrecursionlimit()
    result = check("import time\ntime.sleep(.001)", f"import sys\nassert sys.getrecursionlimit() == {limit}")
    assert result["ok"] is True
    assert sys.getrecursionlimit() == limit


def test_malformed_request_returns_internal_error():
    result = run("pass", mode="unknown")
    assert result["error"]["type"] == "InternalError"
    assert result["ok"] is False
