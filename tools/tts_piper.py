#!/usr/bin/env python3
import argparse
import shlex
import subprocess
import sys
from pathlib import Path

parser = argparse.ArgumentParser(description="Piper CLI wrapper")
parser.add_argument("--text", required=True, help="Path to input text file")
parser.add_argument("--out", required=True, help="Output wav path")
parser.add_argument("--voice", required=True, help="Piper voice model")
parser.add_argument("--piper", required=True, help="Piper binary path")
args = parser.parse_args()

Path(args.out).parent.mkdir(parents=True, exist_ok=True)
cmd = f"{shlex.quote(args.piper)} -m {shlex.quote(args.voice)} -f {shlex.quote(args.text)} -o {shlex.quote(args.out)}"

try:
    subprocess.run(cmd, shell=True, check=True)
except subprocess.CalledProcessError as exc:
    print(f"Piper failed: {exc}", file=sys.stderr)
    sys.exit(exc.returncode or 1)

sys.exit(0)
