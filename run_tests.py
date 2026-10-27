#!/usr/bin/env python3
"""Build every device and run every test: each build.py must write its .amxd as committed, and each test exit 0.

    python3 run_tests.py
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
failed = []
for build in sorted(ROOT.glob("devices/*/*/build.py")):
    before = {p: p.read_bytes() for p in build.parent.glob("*.amxd")}
    if subprocess.run([sys.executable, str(build)], cwd=build.parent).returncode:
        failed.append(str(build.relative_to(ROOT)))
    for p, data in before.items():
        if p.read_bytes() != data:
            failed.append(f"{p.relative_to(ROOT)}: built differs from the committed file")
for test in sorted(ROOT.glob("devices/*/*/test/test_*.py")):
    print(f"== {test.relative_to(ROOT)}", flush=True)
    if subprocess.run([sys.executable, str(test)], cwd=test.parent.parent).returncode:
        failed.append(str(test.relative_to(ROOT)))
print("\n".join(["", f"{len(failed)} failed"] + failed))
sys.exit(1 if failed else 0)
