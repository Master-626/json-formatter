"""CLI interface."""

import json
import math
import os
import tempfile

import click

from json_formatter import __version__


def _reject_non_json_constant(name):
    """Reject NaN and Infinity, which Python accepts but JSON does not."""
    raise ValueError(f"{name} is not valid JSON")


def _parse_finite_float(text):
    """Parse a JSON number without turning it into Infinity or zero.

    Python's ``float`` converts overflow to Infinity and extreme underflow
    to zero. Formatting would then emit a different value, so reject those
    tokens instead. Actual zeros, including ``-0.0``, are preserved.
    """
    number = float(text)
    significand = text.split("e", 1)[0].split("E", 1)[0]
    underflow = number == 0.0 and any(char in "123456789" for char in significand)
    if not math.isfinite(number) or underflow:
        raise ValueError(f"number is out of range: {text}")
    return number


def _load_json(file):
    """Read UTF-8 JSON and report input failures through Click's error stream."""
    try:
        # utf-8-sig strips one leading BOM. Windows editors often add one,
        # and the JSON parser otherwise rejects the whole document.
        with open(file, encoding="utf-8-sig") as stream:
            return json.load(
                stream,
                parse_float=_parse_finite_float,
                parse_constant=_reject_non_json_constant,
            )
    except (OSError, ValueError, RecursionError) as error:
        raise click.ClickException(str(error)) from error


def _format_json(data, indent):
    try:
        return json.dumps(data, indent=indent, allow_nan=False)
    except (RecursionError, ValueError, MemoryError) as error:
        raise click.ClickException(str(error)) from error


def _output_mode(destination):
    """Permission bits for a newly written file."""
    if os.path.exists(destination):
        return os.stat(destination).st_mode & 0o777
    previous_umask = os.umask(0o022)
    os.umask(previous_umask)
    return 0o666 & ~previous_umask


def _write_output(path, text):
    """Atomically replace ``path`` so a failed write leaves the old file intact."""
    if os.path.isdir(path):
        raise click.ClickException(f"Is a directory: '{path}'")
    destination = os.path.realpath(path)
    if os.path.isdir(destination):
        raise click.ClickException(f"Is a directory: '{path}'")
    directory = os.path.dirname(destination) or "."
    temp_path = None
    try:
        fd, temp_path = tempfile.mkstemp(prefix=".jsonfmt-", dir=directory)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        if os.name == "posix":
            os.chmod(temp_path, _output_mode(destination))
        os.replace(temp_path, destination)
    except OSError as error:
        raise click.ClickException(str(error)) from error
    finally:
        if temp_path is not None and os.path.exists(temp_path):
            os.unlink(temp_path)


@click.group()
@click.version_option(version=__version__)
def main():
    """JSON Formatter - Format and validate JSON from the command line."""


@main.command("format")
@click.argument("file")
@click.option(
    "--indent",
    "-i",
    default=2,
    type=click.IntRange(min=0),
    show_default=True,
    help="Indentation spaces (0 or more).",
)
@click.option(
    "--output",
    "-o",
    default=None,
    metavar="FILE",
    help="Write formatted JSON to FILE instead of stdout. '-' keeps stdout.",
)
def format_command(file, indent, output):
    """Format a JSON file."""
    data = _load_json(file)
    # Machine-readable output must never interpret markup, replace emoji names,
    # add terminal styling, or wrap long JSON strings to the terminal width.
    formatted = _format_json(data, indent)
    if output is None or output == "-":
        click.echo(formatted)
    else:
        _write_output(output, formatted + "\n")


@main.command()
@click.argument("file")
def validate(file):
    """Validate a JSON file."""
    _load_json(file)
    click.echo("Valid JSON!")


if __name__ == "__main__":
    main()
