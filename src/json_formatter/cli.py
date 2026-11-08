"""CLI interface."""

import json

import click


def _load_json(file):
    """Read UTF-8 JSON and report input failures through Click's error stream."""
    try:
        with open(file, "r", encoding="utf-8") as stream:
            return json.load(stream)
    except (OSError, ValueError, RecursionError) as error:
        raise click.ClickException(str(error)) from error


@click.group()
@click.version_option(version="0.1.0")
def main():
    """JSON Formatter - Format and validate JSON from the command line."""
    pass


@main.command()
@click.argument("file")
@click.option("--indent", "-i", default=2, help="Indentation spaces")
def format(file, indent):
    """Format a JSON file."""
    data = _load_json(file)
    # Machine-readable output must never interpret markup, replace emoji names,
    # add terminal styling, or wrap long JSON strings to the terminal width.
    try:
        formatted = json.dumps(data, indent=indent)
    except RecursionError as error:
        raise click.ClickException(str(error)) from error
    click.echo(formatted)


@main.command()
@click.argument("file")
def validate(file):
    """Validate a JSON file."""
    _load_json(file)
    click.echo("Valid JSON!")


if __name__ == "__main__":
    main()
