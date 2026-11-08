"""Regression tests for literal, pipe-safe JSON output."""

import inspect
import json
import os
import subprocess
import sys

import pytest
from click.testing import CliRunner

from json_formatter import cli
from json_formatter.cli import main


@pytest.fixture
def runner():
    # Click <8.2 needs this option to expose stderr separately.
    if "mix_stderr" in inspect.signature(CliRunner).parameters:
        return CliRunner(mix_stderr=False)
    return CliRunner()


def write_json(tmp_path, data):
    path = tmp_path / "input.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "data",
    [
        {"text": "[bold]keep[/bold]"},
        {"text": "[/bold]"},
        {"text": "[link=https://example.com]keep[/link]"},
        {"text": ":smile: :warning: :rocket:"},
        {"[red]key[/red]": "[unknown]literal[/unknown]"},
        {"text": r"\[bold]literal\[/bold]"},
        {"text": "x" * 1000},
        {"key " * 100: "long key"},
        {"text": "中文 café 😀"},
        {"text": "line\nnext\ttab\rreturn\u0000nul\u001b[31m"},
        {"text": 'quote: " and backslash: \\'},
        {"nested": [{"[bold]key[/bold]": ":smile:"}, [], {}]},
        ["[bold]keep[/bold]", ":smile:", 1, True, None],
        "[bold]top level[/bold] :smile:",
        123,
        1.25,
        True,
        False,
        None,
        {},
        [],
    ],
)
def test_format_preserves_json_values(runner, tmp_path, data):
    path = write_json(tmp_path, data)
    result = runner.invoke(main, ["format", str(path)])

    assert result.exit_code == 0, result.output
    assert result.stderr == ""
    assert result.stdout == json.dumps(data, indent=2) + "\n"
    assert json.loads(result.stdout) == data
    assert json.loads(path.read_text(encoding="utf-8")) == data


@pytest.mark.parametrize("indent", [0, 1, 4, 8])
def test_format_custom_indentation(runner, tmp_path, indent):
    data = {"nested": [1, {"value": "[bold]keep[/bold]"}]}
    path = write_json(tmp_path, data)
    result = runner.invoke(main, ["format", str(path), "--indent", str(indent)])
    assert result.exit_code == 0
    assert result.stdout == json.dumps(data, indent=indent) + "\n"


@pytest.mark.parametrize("command", ["format", "validate"])
@pytest.mark.parametrize(
    "contents", [b"", b"{bad}", b'{"value": 1,}', b'{} {}', b'{"value":"\xff"}']
)
def test_invalid_input_fails_on_stderr(runner, tmp_path, command, contents):
    path = tmp_path / "invalid[bold].json"
    path.write_bytes(contents)
    result = runner.invoke(main, [command, str(path)])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr.startswith("Error: ")
    assert "Traceback" not in result.stderr
    assert path.read_bytes() == contents


@pytest.mark.parametrize("command", ["format", "validate"])
@pytest.mark.parametrize("kind", ["missing", "directory"])
def test_file_errors_fail_cleanly(runner, tmp_path, command, kind):
    path = tmp_path / "missing[red].json" if kind == "missing" else tmp_path
    result = runner.invoke(main, [command, str(path)])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr.startswith("Error: ")
    assert "Traceback" not in result.stderr
    if kind == "missing":
        assert "missing[red].json" in result.stderr


def test_validate_success(runner, tmp_path):
    path = write_json(tmp_path, {"text": "中文 [bold]keep[/bold] :smile:"})
    result = runner.invoke(main, ["validate", str(path)])
    assert result.exit_code == 0
    assert result.stdout == "Valid JSON!\n"
    assert result.stderr == ""


@pytest.mark.parametrize("command", ["format", "validate"])
def test_integer_digit_limit_fails_cleanly(runner, tmp_path, command):
    limit = getattr(sys, "get_int_max_str_digits", lambda: 0)()
    if limit == 0:
        pytest.skip("This interpreter has no integer digit conversion limit")
    path = tmp_path / "huge-integer.json"
    path.write_text("1" * (limit + 100), encoding="utf-8")
    result = runner.invoke(main, [command, str(path)])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr.startswith("Error: ")
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("command", ["format", "validate"])
def test_parser_recursion_limit_fails_cleanly(runner, tmp_path, command):
    # CPython's C decoder may use a separate limit from Python's call stack.
    depth = max(10_000, sys.getrecursionlimit() + 100)
    path = tmp_path / "deeply-nested.json"
    path.write_text("[" * depth + "0" + "]" * depth, encoding="utf-8")
    result = runner.invoke(main, [command, str(path)])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr.startswith("Error: ")
    assert "Traceback" not in result.stderr


def test_serializer_recursion_limit_fails_cleanly(runner, monkeypatch):
    # Parser and serializer limits differ across Python versions. Simulate only
    # the serializer failure so this check does not depend on either threshold.
    def fail_serialization(*args, **kwargs):
        raise RecursionError("maximum recursion depth exceeded")

    monkeypatch.setattr(cli, "_load_json", lambda file: {})
    monkeypatch.setattr(cli.json, "dumps", fail_serialization)
    result = runner.invoke(main, ["format", "unused.json"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr.startswith("Error: ")
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("encoding", ["ascii", "utf-8"])
def test_format_redirected_stdout_is_valid_json(tmp_path, encoding):
    data = {"[bold]key[/bold]": "中文 :smile: " + "x" * 1000}
    path = write_json(tmp_path, data)
    output = tmp_path / "formatted.json"
    env = dict(os.environ, COLUMNS="12", TERM="xterm-256color", FORCE_COLOR="1")
    env["PYTHONIOENCODING"] = encoding

    with output.open("wb") as stream:
        result = subprocess.run(
            [sys.executable, "-m", "json_formatter.cli", "format", str(path)],
            stdout=stream,
            stderr=subprocess.PIPE,
            env=env,
            check=False,
        )

    assert result.returncode == 0, result.stderr
    assert result.stderr == b""
    assert json.loads(output.read_text(encoding="utf-8")) == data
    assert "\x1b" not in output.read_text(encoding="utf-8")


@pytest.mark.parametrize("command", ["format", "validate"])
def test_invalid_json_subprocess_exit_status(tmp_path, command):
    path = tmp_path / "invalid.json"
    path.write_text("{bad}", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "json_formatter.cli", command, str(path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 1
    assert result.stdout == b""
    assert result.stderr.startswith(b"Error: ")
    assert b"Traceback" not in result.stderr


def test_version(runner):
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.stdout


def test_help(runner):
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "format" in result.stdout
    assert "validate" in result.stdout
