"""Minimal testing helpers for the Typer shim."""

from __future__ import annotations

import io
import traceback
from contextlib import redirect_stdout, redirect_stderr


class Result:
    def __init__(self, exit_code: int, stdout: str, stderr: str) -> None:
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr


class CliRunner:
    def invoke(self, app, args):
        stdout = io.StringIO()
        stderr = io.StringIO()
        exit_code = 0
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                app._invoke(list(args))
            except SystemExit as exc:
                exit_code = int(exc.code) if exc.code is not None else 0
            except Exception:
                exit_code = 1
                traceback.print_exc(file=stderr)
        return Result(exit_code, stdout.getvalue(), stderr.getvalue())
