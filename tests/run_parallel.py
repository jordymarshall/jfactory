#!/usr/bin/env python3
"""Run every tests/test_*.py file at once, in separate processes, so CI's unit suite stays under its two-minute bar
(.jfactory/standards.md, Performance) without dropping any test. Prints each file's output, the total number of tests
run and the wall time; exits non-zero if any file fails or no tests ran.

  python3 tests/run_parallel.py [--jobs 4]
"""
import argparse
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run(path):
    started = time.monotonic()
    proc = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', str(HERE), '-p', path.name, '-v'],
                          capture_output=True, text=True, cwd=HERE.parent)
    ran = re.search(r'^Ran (\d+) tests?', proc.stderr, re.M)
    return path.name, proc.returncode, int(ran.group(1)) if ran else 0, time.monotonic() - started, proc.stderr


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    started = time.monotonic()
    files = sorted(HERE.glob('test_*.py'))
    with ThreadPoolExecutor(args.jobs) as pool:
        results = list(pool.map(run, files))
    failed = [name for name, code, *_ in results if code]
    for name, code, count, seconds, output in results:
        print(f'===== {name}: {"FAILED" if code else "ok"}, {count} tests, {seconds:.1f}s')
        if code:
            print(output)
    total = sum(count for _, _, count, _, _ in results)
    print(f'Ran {total} tests in {len(files)} files in {time.monotonic() - started:.1f}s wall time'
          + (f'; FAILED: {", ".join(failed)}' if failed else '; OK'))
    return 1 if failed or not total else 0


if __name__ == '__main__':
    sys.exit(main())
