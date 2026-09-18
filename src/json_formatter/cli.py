"""CLI interface."""
import click
import json
from rich.console import Console

console = Console()

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
    try:
        with open(file, "r") as f:
            data = json.load(f)
        formatted = json.dumps(data, indent=indent)
        console.print(formatted)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")

@main.command()
@click.argument("file")
def validate(file):
    """Validate a JSON file."""
    try:
        with open(file, "r") as f:
            json.load(f)
        console.print("[bold green]✓ Valid JSON![/bold green]")
    except Exception as e:
        console.print(f"[bold red]✗ Invalid JSON: {e}[/bold red]")

if __name__ == "__main__":
    main()
