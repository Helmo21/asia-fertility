#!/usr/bin/env python3
"""One-shot FertiScope demo. Run from project root with the venv activated:

    source .venv/bin/activate
    python demo.py

Equivalent to: `fertiscope demo` once the package is installed via pip install -e .
"""
from fertiscope.cli import cmd_demo
import argparse


if __name__ == "__main__":
    ns = argparse.Namespace(tokenizers=None)
    cmd_demo(ns)
