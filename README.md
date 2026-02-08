# nbaio

[![PyPI](https://img.shields.io/pypi/v/nbaio.svg)](https://pypi.org/project/nbaio/)
[![Changelog](https://img.shields.io/github/v/release/mse11/nbaio?include_prereleases&label=changelog)](https://github.com/mse11/nbaio/releases)
[![Tests](https://github.com/mse11/nbaio/actions/workflows/test.yml/badge.svg)](https://github.com/mse11/nbaio/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/mse11/nbaio/blob/master/LICENSE)

Simple async helper with IU support 

## Installation

Install this tool using `pip`:
```bash
pip install nbaio
```
## Usage

For help, run:
```bash
nbaio --help
```
You can also use:
```bash
python -m nbaio --help
```
## Development

To contribute to this tool, first checkout the code. Then create a new virtual environment:
```bash
cd nbaio
python -m venv venv
source venv/bin/activate
```
Now install the dependencies and test dependencies:
```bash
pip install -e '.[test]'
```
To run the tests:
```bash
python -m pytest
```
