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
def test_nested_input_follows_python_limits(runner, tmp_path, command):
    # Newer Python versions can parse deeper JSON without a recursion error.
    # Follow this interpreter's result rather than imposing an arbitrary limit.
    depth = sys.getrecursionlimit() + 100
    source = "[" * depth + "0" + "]" * depth
    path = tmp_path / "deeply-nested.json"
    path.write_text(source, encoding="utf-8")
    try:
        data = json.loads(source)
        if command == "format":
            expected = json.dumps(data, indent=2) + "\n"
        else:
            expected = "Valid JSON!\n"
    except RecursionError:
        expected = None

    result = runner.invoke(main, [command, str(path)])
    if expected is not None:
        assert result.exit_code == 0
        assert result.stdout == expected
        assert result.stderr == ""
    else:
        assert result.exit_code == 1
        assert result.stdout == ""
        assert result.stderr.startswith("Error: ")
        assert "Traceback" not in result.stderr


@pytest.mark.parametrize("command", ["format", "validate"])
def test_parser_recursion_limit_fails_cleanly(runner, tmp_path, monkeypatch, command):
    def fail_parsing(*args, **kwargs):
        raise RecursionError("maximum recursion depth exceeded")

    path = write_json(tmp_path, {})
    monkeypatch.setattr(cli.json, "load", fail_parsing)
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
        capture_output=True,
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


def test_format_help_lists_options(runner):
    result = runner.invoke(main, ["format", "--help"])
    assert result.exit_code == 0
    assert "--indent" in result.stdout
    assert "--output" in result.stdout


def test_missing_command_is_usage_error(runner):
    result = runner.invoke(main, [])
    assert result.exit_code == 2
    assert "format" in result.output
    assert "validate" in result.output


def test_format_does_not_modify_input_bytes(runner, tmp_path):
    path = tmp_path / "input.json"
    original = b'{\n"a" : 1}\n'
    path.write_bytes(original)
    result = runner.invoke(main, ["format", str(path)])
    assert result.exit_code == 0
    assert result.stdout == '{\n  "a": 1\n}\n'
    assert path.read_bytes() == original


def test_duplicate_keys_keep_the_last_value(runner, tmp_path):
    path = tmp_path / "dup.json"
    path.write_text('{"a": 1, "a": 2}', encoding="utf-8")
    result = runner.invoke(main, ["format", str(path)])
    assert result.exit_code == 0
    assert result.stdout == '{\n  "a": 2\n}\n'
    assert json.loads(result.stdout) == {"a": 2}


def test_number_spelling_is_normalized(runner, tmp_path):
    path = tmp_path / "number.json"
    path.write_text("1e2", encoding="utf-8")
    result = runner.invoke(main, ["format", str(path)])
    assert result.exit_code == 0
    assert result.stdout == "100.0\n"


def test_negative_zero_is_preserved(runner, tmp_path):
    path = tmp_path / "negzero.json"
    path.write_text("-0.0", encoding="utf-8")
    result = runner.invoke(main, ["format", str(path)])
    assert result.exit_code == 0
    assert result.stdout == "-0.0\n"


@pytest.mark.parametrize(
    "contents, expected",
    [
        ("0", "0\n"),
        ("0.0", "0.0\n"),
        ("-0", "0\n"),
        ("0e0", "0.0\n"),
        ("0e-400", "0.0\n"),
        ("-0e309", "-0.0\n"),
        ("0.000", "0.0\n"),
    ],
)
def test_actual_zeros_are_formatted(runner, tmp_path, contents, expected):
    path = tmp_path / "zero.json"
    path.write_text(contents, encoding="utf-8")
    result = runner.invoke(main, ["format", str(path)])
    assert result.exit_code == 0, result.stderr
    assert result.stdout == expected


@pytest.mark.parametrize("contents", ["1e308", "5e-324", "1e-323", "1.25"])
def test_finite_edge_numbers_are_formatted(runner, tmp_path, contents):
    path = tmp_path / "finite.json"
    path.write_text(contents, encoding="utf-8")
    result = runner.invoke(main, ["format", str(path)])
    assert result.exit_code == 0, result.stderr
    assert result.stdout.strip() not in {"Infinity", "-Infinity", "NaN", "0.0"}
    assert json.loads(result.stdout) != 0


def test_number_like_strings_are_preserved(runner, tmp_path):
    path = tmp_path / "strings.json"
    path.write_text('{"big": "1e309", "name": "NaN"}', encoding="utf-8")
    result = runner.invoke(main, ["format", str(path)])
    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout) == {"big": "1e309", "name": "NaN"}


@pytest.mark.parametrize("command", ["format", "validate"])
@pytest.mark.parametrize(
    "contents",
    [
        "1e309",
        "-1e309",
        "1.8e308",
        "1e-324",
        "1e-400",
        "-1e-400",
        "NaN",
        "Infinity",
        "-Infinity",
        "[1, NaN]",
        '{"n": Infinity}',
    ],
)
def test_non_json_numbers_fail(runner, tmp_path, command, contents):
    path = tmp_path / "bad-number.json"
    path.write_text(contents, encoding="utf-8")
    result = runner.invoke(main, [command, str(path)])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr.startswith("Error: ")
    assert "Traceback" not in result.stderr
    assert path.read_text(encoding="utf-8") == contents


@pytest.mark.parametrize("command", ["format", "validate"])
def test_utf8_bom_is_accepted(runner, tmp_path, command):
    path = tmp_path / "bom.json"
    original = b'\xef\xbb\xbf{"text": "\xe4\xb8\xad\xe6\x96\x87"}'
    path.write_bytes(original)
    result = runner.invoke(main, [command, str(path)])
    assert result.exit_code == 0, result.stderr
    if command == "format":
        assert result.stdout == '{\n  "text": "\\u4e2d\\u6587"\n}\n'
    else:
        assert result.stdout == "Valid JSON!\n"
    assert path.read_bytes() == original


@pytest.mark.parametrize("command", ["format", "validate"])
def test_bom_does_not_hide_invalid_json(runner, tmp_path, command):
    path = tmp_path / "bom-bad.json"
    path.write_bytes(b"\xef\xbb\xbf{bad}")
    result = runner.invoke(main, [command, str(path)])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("command", ["format", "validate"])
def test_utf16_is_rejected(runner, tmp_path, command):
    path = tmp_path / "utf16.json"
    path.write_bytes('{"a": 1}'.encode("utf-16"))
    result = runner.invoke(main, [command, str(path)])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr.startswith("Error: ")


@pytest.mark.parametrize("args", [["-i", "-1"], ["--indent", "-5"], ["--indent=-1"]])
def test_negative_indent_is_usage_error(runner, tmp_path, args):
    path = write_json(tmp_path, {"a": 1})
    before = path.read_bytes()
    result = runner.invoke(main, ["format", str(path), *args])
    assert result.exit_code == 2
    assert result.stdout == ""
    assert "Traceback" not in result.stderr
    assert path.read_bytes() == before


def test_serializer_memory_error_fails_cleanly(runner, monkeypatch):
    def fail_serialization(*args, **kwargs):
        raise MemoryError("out of memory")

    monkeypatch.setattr(cli, "_load_json", lambda file: {})
    monkeypatch.setattr(cli.json, "dumps", fail_serialization)
    result = runner.invoke(main, ["format", "unused.json"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr.startswith("Error: ")
    assert "Traceback" not in result.stderr


def test_output_writes_file_and_leaves_stdout_empty(runner, tmp_path):
    source = tmp_path / "in.json"
    original = b'{"a" : 1}'
    source.write_bytes(original)
    dest = tmp_path / "out.json"
    result = runner.invoke(main, ["format", str(source), "-o", str(dest)])
    assert result.exit_code == 0, result.stderr
    assert result.stdout == ""
    assert result.stderr == ""
    assert source.read_bytes() == original
    assert dest.read_bytes() == b'{\n  "a": 1\n}\n'


def test_output_dash_is_stdout(runner, tmp_path):
    path = write_json(tmp_path, {"a": 1})
    result = runner.invoke(main, ["format", str(path), "--output", "-"])
    assert result.exit_code == 0
    assert result.stdout == '{\n  "a": 1\n}\n'


def test_inplace_output_replaces_file(runner, tmp_path):
    path = tmp_path / "data.json"
    path.write_text('{"a":1,"b":[1,2]}', encoding="utf-8")
    result = runner.invoke(main, ["format", str(path), "-o", str(path), "-i", "4"])
    assert result.exit_code == 0, result.stderr
    assert result.stdout == ""
    expected = json.dumps({"a": 1, "b": [1, 2]}, indent=4) + "\n"
    assert path.read_text(encoding="utf-8") == expected
    assert list(tmp_path.glob(".jsonfmt-*")) == []


def test_invalid_json_does_not_create_output(runner, tmp_path):
    source = tmp_path / "bad.json"
    source.write_text("{bad}", encoding="utf-8")
    dest = tmp_path / "out.json"
    result = runner.invoke(main, ["format", str(source), "-o", str(dest)])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert not dest.exists()
    assert source.read_text(encoding="utf-8") == "{bad}"


def test_output_directory_fails(runner, tmp_path):
    source = write_json(tmp_path, {"a": 1})
    result = runner.invoke(main, ["format", str(source), "-o", str(tmp_path)])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "directory" in result.stderr.lower()
    assert "Traceback" not in result.stderr


def test_missing_output_directory_fails(runner, tmp_path):
    source = write_json(tmp_path, {"a": 1})
    before = source.read_bytes()
    dest = tmp_path / "missing" / "out.json"
    result = runner.invoke(main, ["format", str(source), "-o", str(dest)])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Traceback" not in result.stderr
    assert source.read_bytes() == before
    assert not dest.exists()


def test_failed_replace_keeps_existing_files(runner, tmp_path, monkeypatch):
    source = tmp_path / "in.json"
    source.write_text('{"a": 1}', encoding="utf-8")
    dest = tmp_path / "out.json"
    dest.write_text("keep\n", encoding="utf-8")

    def fail_replace(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(cli.os, "replace", fail_replace)
    result = runner.invoke(main, ["format", str(source), "-o", str(dest)])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "disk full" in result.stderr
    assert "Traceback" not in result.stderr
    assert dest.read_text(encoding="utf-8") == "keep\n"
    assert source.read_text(encoding="utf-8") == '{"a": 1}'
    assert list(tmp_path.glob(".jsonfmt-*")) == []


def test_output_follows_symlink(runner, tmp_path):
    if os.name != "posix":
        pytest.skip("symlink replacement is checked on POSIX")
    real = tmp_path / "real.json"
    real.write_text('{"a":1}', encoding="utf-8")
    link = tmp_path / "link.json"
    link.symlink_to(real.name)
    result = runner.invoke(main, ["format", str(link), "-o", str(link)])
    assert result.exit_code == 0, result.stderr
    assert link.is_symlink()
    assert real.read_text(encoding="utf-8") == '{\n  "a": 1\n}\n'


def test_new_output_respects_umask(runner, tmp_path):
    if os.name != "posix":
        pytest.skip("umask file modes are POSIX-specific")
    source = write_json(tmp_path, {"a": 1})
    dest = tmp_path / "out.json"
    result = runner.invoke(main, ["format", str(source), "-o", str(dest)])
    assert result.exit_code == 0, result.stderr
    previous = os.umask(0o022)
    os.umask(previous)
    assert dest.stat().st_mode & 0o777 == 0o666 & ~previous


def test_inplace_output_keeps_its_mode(runner, tmp_path):
    if os.name != "posix":
        pytest.skip("preserving file modes is POSIX-specific")
    path = tmp_path / "data.json"
    path.write_text('{"a":1}', encoding="utf-8")
    path.chmod(0o604)
    result = runner.invoke(main, ["format", str(path), "-o", str(path)])
    assert result.exit_code == 0, result.stderr
    assert path.stat().st_mode & 0o777 == 0o604
    assert path.read_text(encoding="utf-8") == '{\n  "a": 1\n}\n'


def test_existing_output_keeps_its_mode(runner, tmp_path):
    if os.name != "posix":
        pytest.skip("preserving file modes is POSIX-specific")
    source = write_json(tmp_path, {"a": 1})
    dest = tmp_path / "out.json"
    dest.write_text("old\n", encoding="utf-8")
    dest.chmod(0o640)
    result = runner.invoke(main, ["format", str(source), "-o", str(dest)])
    assert result.exit_code == 0, result.stderr
    assert dest.stat().st_mode & 0o777 == 0o640
    assert dest.read_text(encoding="utf-8") == '{\n  "a": 1\n}\n'


def test_out_of_range_number_subprocess(tmp_path):
    path = tmp_path / "big.json"
    path.write_text("1e309", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "json_formatter.cli", "format", str(path)],
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1
    assert result.stdout == b""
    assert b"out of range" in result.stderr
    assert b"Traceback" not in result.stderr


def test_negative_indent_subprocess(tmp_path):
    path = tmp_path / "data.json"
    path.write_text("{}", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "json_formatter.cli", "format", "-i", "-1", str(path)],
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2
    assert result.stdout == b""
    assert b"Traceback" not in result.stderr


def test_output_file_subprocess(tmp_path):
    source = tmp_path / "in.json"
    source.write_text('{"a":1}', encoding="utf-8")
    dest = tmp_path / "out.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "json_formatter.cli",
            "format",
            str(source),
            "-o",
            str(dest),
        ],
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == b""
    assert result.stderr == b""
    assert dest.read_text(encoding="utf-8") == '{\n  "a": 1\n}\n'
