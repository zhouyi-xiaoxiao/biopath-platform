"""Minimal pytest-compatible shim for offline execution."""

from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path
from types import ModuleType
from typing import Callable, List, Tuple


def approx(expected, rel=1e-12, abs=0.0):
    class _Approx:
        def __init__(self, value):
            self.value = value

        def __eq__(self, other):
            diff = abs(other - self.value)
            return diff <= max(abs, rel * abs(self.value))

    return _Approx(expected)


def _load_module(path: Path) -> ModuleType:
    module_name = path.stem + "_" + str(abs(hash(path)))
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _discover_tests(root: Path) -> List[Tuple[str, Callable[[], None]]]:
    tests: List[Tuple[str, Callable[[], None]]] = []
    for path in sorted(root.rglob("test_*.py")):
        module = _load_module(path)
        for name, obj in module.__dict__.items():
            if callable(obj) and name.startswith("test_"):
                tests.append((f"{path.name}::{name}", obj))
    return tests


def main(args=None) -> int:
    root = Path.cwd()
    sys.path.insert(0, str(root))
    quiet = False
    if args is None:
        args = sys.argv[1:]
    for arg in args:
        if arg in {"-q", "--quiet"}:
            quiet = True

    tests = _discover_tests(root / "tests")
    failures = 0
    for name, func in tests:
        try:
            func()
            if not quiet:
                print(f"PASS {name}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL {name}: {exc}")
        except Exception as exc:
            failures += 1
            print(f"ERROR {name}: {exc}")

    if not quiet:
        total = len(tests)
        passed = total - failures
        print(f"{passed} passed, {failures} failed")

    return 0 if failures == 0 else 1
