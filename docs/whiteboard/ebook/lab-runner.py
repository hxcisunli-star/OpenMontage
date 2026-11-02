"""页内 Python 练习的运行器；也可直接在 CPython 中使用。"""

import builtins
from contextlib import contextmanager, redirect_stderr, redirect_stdout
import io
import random
import time
import traceback


_FILENAME = "<练习>"
_MAX_LINES = 200
_MAX_CHARS = 16384
_TRUNCATION = "……输出太长，已截断"
_INPUT_ERROR = "页内练习不支持 input() 输入：请直接把值写进变量"
_PUNCTUATION = dict(zip(
    "（）：，。“”‘’；【】｛｝＝＋－＊／％＜＞！＃＠＆｜＾～＼",
    "():,.\"\"'';[]{}=+-*/%<>!#@&|^~\\",
))


class _Output(io.TextIOBase):
    """只保留有限的文本；写入方仍收到完整的字符计数。"""

    def __init__(self):
        self._text = ""
        self._newlines = 0
        self.truncated = False

    @property
    def encoding(self):
        return "utf-8"

    def writable(self):
        return True

    def write(self, text):
        if not isinstance(text, str):
            raise TypeError("write() argument must be str")
        length = len(text)
        if not length:
            return 0
        end = min(length, _MAX_CHARS - len(self._text))
        if self._newlines >= _MAX_LINES:
            end = 0
        else:
            position = 0
            for _ in range(_MAX_LINES - self._newlines):
                newline = text.find("\n", position, end)
                if newline < 0:
                    break
                position = newline + 1
            else:
                end = position
        kept = text[:end]
        self._text += kept
        self._newlines += kept.count("\n")
        self.truncated |= end < length
        return length

    def getvalue(self):
        if not self.truncated:
            return self._text
        separator = "" if self._text.endswith("\n") else "\n"
        return self._text + separator + _TRUNCATION + "\n"


def _no_input(*args, **kwargs):
    raise RuntimeError(_INPUT_ERROR)


@contextmanager
def _runtime_state():
    state = random.getstate()
    original_input = builtins.input
    builtins.input = _no_input
    try:
        yield
    finally:
        builtins.input = original_input
        random.setstate(state)


def _namespace():
    return {"__name__": "__main__", "__builtins__": builtins.__dict__.copy()}


def _message(error):
    try:
        return str(error)
    except BaseException:
        return "无法读取异常消息"


def _hint(error, code):
    message = _message(error)
    if isinstance(error, SyntaxError):
        line = error.text or ""
        column = error.offset or 1
        character = line[column - 1:column]
        if character not in _PUNCTUATION and "invalid character" in message:
            character = next((c for c in line if c in _PUNCTUATION), "")
            if character:
                column = line.index(character) + 1
        if character in _PUNCTUATION:
            return (f"第 {error.lineno} 行第 {column} 列的“{character}”是全角标点，"
                    f"请改成半角“{_PUNCTUATION[character]}”。")
        if isinstance(error, TabError):
            return "缩进混用了 Tab 和空格。请统一用空格，每层缩进 4 个空格。"
        if "expected an indented block" in message:
            return "冒号后需要缩进的代码块。请把下一行向右缩进 4 个空格。"
        if "unexpected indent" in message:
            return "这一行多缩进了。请和同一层的代码左边对齐。"
        if isinstance(error, IndentationError):
            return "缩进没有对齐。请用 4 个空格缩进同一层代码，别混用 Tab。"
        if any(part in message for part in ("was never closed", "unmatched", "does not match", "unexpected EOF")):
            return "括号没有配对。请检查这一行和前面的代码，把圆括号、方括号或花括号补齐。"
        return "这行的写法不符合 Python 语法。请检查冒号、引号和括号是否写全。"
    if message == _INPUT_ERROR:
        return _INPUT_ERROR
    if isinstance(error, NameError) and set(getattr(error, "name", None) or "x") == {"_"}:
        return "代码里还有没填的空白 ___，请把它换成你自己的代码。"        # fill-in-the-blank starters
    hints = (
        (NameError, "这个名字还没定义。请检查拼写，并先给变量赋值再使用。"),
        (TypeError, "值的类型用错了。请检查运算两边或函数参数，必要时用 int()、str() 转换。"),
        (ZeroDivisionError, "除数不能是 0。请检查除号或取余符号右边的值，再计算。"),
        (IndexError, "下标超出了范围。序号从 0 开始，请先检查列表或字符串的长度。"),
        (KeyError, "字典里没有这个键。请检查键的拼写，或先判断键是否存在。"),
        (ValueError, "值的内容不合要求。请检查输入的值，例如 int() 需要能转成整数的文字。"),
        (ModuleNotFoundError, "这个练习只能用 Python 自带的库。请检查库名，去掉需要另行安装的库。"),
        (AttributeError, "这个值没有你使用的属性或方法。请检查拼写，以及变量当前是什么类型。"),
        (RecursionError, "函数调用自己的次数太多了。请添加能结束递归的条件，并检查参数是否在变化。"),
    )
    return next((hint for kind, hint in hints if isinstance(error, kind)),
                "程序在这里停下了。请根据错误消息检查这一行使用的值和操作。")


def _error(error, code, kind=None):
    name = kind or type(error).__name__
    message = _message(error)
    frames = [frame for frame in traceback.extract_tb(error.__traceback__)
              if frame.filename == _FILENAME]
    lineno = frames[-1].lineno if frames else None
    colno = None
    lines = code.splitlines()
    rendered = []
    if isinstance(error, SyntaxError) and kind is None:
        lineno, colno = error.lineno, error.offset
        rendered.append(f'  File "{_FILENAME}", line {lineno}\n')
        source = error.text.rstrip("\r\n") if error.text else ""
        if source:
            rendered.append(f"    {source}\n")
            if colno:
                rendered.append("    " + " " * (colno - 1) + "^\n")
    elif frames:
        rendered.append("Traceback (most recent call last):\n")
        for frame in frames:
            rendered.append(f'  File "{_FILENAME}", line {frame.lineno}, in {frame.name}\n')
            if 0 < frame.lineno <= len(lines):
                rendered.append(f"    {lines[frame.lineno - 1].strip()}\n")
    rendered.append(f"{name}: {message}\n")
    if kind == "PreludeError":
        hint = "练习准备代码出错了，请联系课程作者检查练习配置。"
    elif kind == "InternalError":
        hint = "运行环境出错了，请重试；如果仍然失败，请重新打开页面。"
    else:
        hint = _hint(error, code)
    return {"type": name, "message": message, "lineno": lineno,
            "colno": colno, "hintZh": hint, "traceback": "".join(rendered)}


def _prelude(prelude, namespace):
    with redirect_stdout(_Output()), redirect_stderr(_Output()):
        exec(compile(prelude, "<练习准备>", "exec"), namespace)


def run_request(mode, code, prelude, tests, seed):
    """运行一次请求，所有返回值都是可直接 JSON 序列化的标准类型。"""
    started = time.perf_counter()
    stdout, stderr = _Output(), _Output()
    result = {"ok": False, "stdout": "", "stderr": "", "truncated": False,
              "durationMs": 0, "error": None, "checks": []}
    try:
        if mode not in ("run", "check"):
            raise ValueError("未知的运行模式")
        try:
            compiled = compile(code, _FILENAME, "exec")
        except SyntaxError as error:
            result["error"] = _error(error, code)
            return result

        def run_with_seed(run_seed):
            with _runtime_state():
                namespace = _namespace()
                _prelude(prelude, namespace)
                random.seed(run_seed)
                output = _Output()
                with redirect_stdout(output), redirect_stderr(_Output()):
                    exec(compiled, namespace)
                return output.getvalue()

        with _runtime_state():
            namespace = _namespace()
            try:
                _prelude(prelude, namespace)
            except BaseException as error:
                result["error"] = _error(error, code, "PreludeError")
                return result
            if seed is not None:
                random.seed(seed)
            try:
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    exec(compiled, namespace)
            except BaseException as error:
                result["error"] = _error(error, code)
            if result["error"] is None and mode == "check":
                for test in tests:
                    check = {"id": test["id"], "name": test["name"],
                             "passed": True, "message": ""}
                    check_namespace = _namespace()
                    check_namespace.update(USER_CODE=code, STDOUT=stdout.getvalue(),
                                           NS=namespace, RUN_WITH_SEED=run_with_seed)
                    try:
                        with redirect_stdout(_Output()), redirect_stderr(_Output()):
                            exec(compile(test["code"], "<练习检查>", "exec"), check_namespace)
                    except AssertionError as error:
                        check.update(passed=False, message=_message(error))
                    except BaseException as error:
                        check.update(passed=False, message=f"检查代码出错：{type(error).__name__}: {_message(error)}")
                    result["checks"].append(check)
            result["ok"] = result["error"] is None and all(
                check["passed"] for check in result["checks"])
    except BaseException as error:
        result["ok"] = False
        result["error"] = _error(error, code, "InternalError")
    finally:
        result.update(stdout=stdout.getvalue(), stderr=stderr.getvalue(),
                      truncated=stdout.truncated or stderr.truncated,
                      durationMs=(time.perf_counter() - started) * 1000)
    return result
