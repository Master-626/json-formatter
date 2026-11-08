# JSON Formatter

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Developer Tool](https://img.shields.io/badge/developer-tool-green.svg)]()

A JSON formatting and validation CLI tool.

## ✨ Features

- **Format** - Pretty-print JSON with custom indentation
- **Validate** - Check if JSON is valid
- **Easy to Use** - Simple command-line interface
- **Fast** - Instant formatting and validation

## 📦 Installation

```bash
git clone https://github.com/Master-626/json-formatter.git
cd json-formatter
pip install .
```

## 🚀 Quick Start

```bash
# Format a JSON file
jsonfmt format data.json -i 4

# Validate JSON
jsonfmt validate data.json
```

## Output and errors

Input files are read as UTF-8. `format` writes only formatted JSON to stdout,
with a trailing newline. JSON string values remain literal, including Rich-style
tags such as `[bold]text[/bold]`, emoji names such as `:smile:`, and long lines.
Unicode is JSON-escaped in the output, so the result also works with ASCII-only
terminal encodings.

```bash
# Save formatted JSON to a different file
jsonfmt format data.json > formatted.json

# Validation failures can be checked by scripts
jsonfmt validate data.json && echo "Ready to use"
```

`validate` prints `Valid JSON!` on success. Invalid JSON, unreadable files,
invalid UTF-8, and parser/serializer integer or nesting limits produce an error on
stderr and exit status 1, with no stdout.
Command-line usage errors return status 2. Input files are never modified by
the tool. Do not redirect output to the input file: the shell truncates it before
the command runs.

Formatting and validation use Python's standard `json` parser. Formatting is not
a byte-for-byte round trip: whitespace, number spelling, and escape sequences are
normalized, and duplicate object keys follow the parser's last-value behavior.

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

## 📄 License

MIT License
