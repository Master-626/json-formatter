# JSON Formatter

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/Master-626/json-formatter/actions/workflows/test.yml/badge.svg)](https://github.com/Master-626/json-formatter/actions/workflows/test.yml)

## 中文简介

`jsonfmt` 是一个轻量的命令行工具，用来格式化 JSON，或检查文件是不是合法 JSON。默认把结果写到标准输出，不修改原文件；也可以用 `-o` 把格式化结果安全地写入另一个文件（包括原地覆盖）。输入按 UTF-8 读取，并接受文件开头的 BOM。非法 JSON、超出范围的数字、`NaN` / `Infinity`，以及负数缩进，都会在标准错误中报告并以非零状态退出。安装、选项和测试方法见下方英文说明。

## Purpose

`jsonfmt` pretty-prints a JSON file, or checks that the file is valid JSON. It is meant for shells and scripts: successful `format` writes only JSON, and failures write only an error on stderr.

Formatting uses Python's `json` parser. It is not a byte-for-byte round trip. Whitespace, number spelling, and escape sequences are normalized, and duplicate object keys keep the parser's last value. Object key order is preserved.

## Installation

Python 3.8 or newer is required.

```bash
git clone https://github.com/Master-626/json-formatter.git
cd json-formatter
python -m pip install .
```

The install adds a `jsonfmt` command. For local development, install the test and lint tools too:

```bash
python -m pip install -e ".[dev]"
```

## Usage

```bash
# Pretty-print a file to stdout (default indent is 2)
jsonfmt format data.json

# Use a different indent and save to another file
jsonfmt format data.json -i 4 -o formatted.json

# Replace the file in place. The tool reads it fully, then replaces it atomically.
jsonfmt format data.json -o data.json

# Check a file from a script
jsonfmt validate data.json && echo "Ready to use"

# Shell redirection also works when the destination is a different file
jsonfmt format data.json > formatted.json
```

Do not redirect the shell onto the input file (`jsonfmt format data.json > data.json`). The shell truncates that file before the program runs. Use `-o data.json` to format in place.

## Options

`jsonfmt --help` lists the commands. `jsonfmt --version` prints the version.

### `jsonfmt format FILE`

| Option | Description |
| --- | --- |
| `-i`, `--indent INTEGER` | Spaces per indent level. Default: `2`. Must be `0` or greater. `0` inserts newlines without extra indentation; it does not minify the document. |
| `-o`, `--output FILE` | Write formatted JSON to `FILE` instead of stdout. `-` keeps stdout. Line endings in the file are LF. |

`format` prints the JSON and a trailing newline to stdout when `--output` is omitted. With a real output path it prints nothing on success. An existing output file is replaced only after the new contents are written. On POSIX, that file keeps its permission bits; a new file uses the process umask. A symlink output path is followed, so the link itself stays a link.

### `jsonfmt validate FILE`

Prints `Valid JSON!` and exits `0` when the file contains one JSON value. No other stdout is written.

## Output and errors

Input files are read as UTF-8. A single leading UTF-8 BOM is accepted and left in the input file; other encodings, including UTF-16, are rejected.

JSON string values stay literal. Rich-style tags such as `[bold]text[/bold]`, emoji names such as `:smile:`, and long lines are not interpreted or wrapped. Unicode in strings is escaped (`\uXXXX`), so the output is ASCII and can be printed on an ASCII-only terminal.

Exit status:

| Status | Meaning |
| --- | --- |
| `0` | Success. |
| `1` | Invalid JSON, unreadable path, invalid UTF-8, a number that does not fit in a finite binary64 value, or a parser/serializer limit. The message goes to stderr and stdout is empty. |
| `2` | Command-line usage error, including a negative `--indent` or an unknown command. |

`NaN`, `Infinity`, and `-Infinity` are not JSON. Numbers that overflow to infinity (for example `1e309`) or underflow to zero (for example `1e-400`) are rejected instead of being rewritten as `Infinity` or `0.0`. Actual zeros such as `0`, `0.0`, `-0.0`, and `0e-400` are kept. The input file is never modified unless you pass it as `--output`.

## Running tests

```bash
python -m pip install -e ".[dev]"
python -m ruff check .
python -m pytest
```

GitHub Actions runs both `ruff check` and `pytest` on Python 3.8 through 3.14 (3.8 on Ubuntu 22.04), and also runs the suite on Windows and macOS.

## License

MIT License
