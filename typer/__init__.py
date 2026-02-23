"""Minimal Typer-compatible shim for offline execution."""

from __future__ import annotations

import inspect
import os
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union, get_args, get_origin, get_type_hints


class BadParameter(ValueError):
    pass


@dataclass
class OptionInfo:
    default: Any
    param_decls: List[str]
    min: int | None = None
    exists: bool | None = None
    dir_okay: bool | None = None
    readable: bool | None = None


def Option(default: Any, *param_decls: str, **kwargs: Any) -> OptionInfo:
    decls: List[str] = []
    for decl in param_decls:
        if isinstance(decl, str) and "/" in decl:
            decls.extend(decl.split("/"))
        else:
            decls.append(decl)
    if not decls:
        decls = []
    return OptionInfo(default=default, param_decls=decls, **kwargs)


def echo(message: str) -> None:
    print(message)


class Typer:
    def __init__(self, add_completion: bool = True) -> None:
        self._commands: Dict[str, Callable[..., Any]] = {}

    def command(self, name: str | None = None):
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            cmd_name = name or func.__name__
            self._commands[cmd_name] = func
            return func

        return decorator

    def _invoke(self, args: List[str]) -> None:
        if not args:
            raise SystemExit(1)
        cmd_name = args[0]
        if cmd_name not in self._commands:
            raise SystemExit(1)
        func = self._commands[cmd_name]
        params = inspect.signature(func).parameters
        type_hints = get_type_hints(func)

        option_map: Dict[str, str] = {}
        option_info: Dict[str, OptionInfo] = {}
        values: Dict[str, Any] = {}

        for param_name, param in params.items():
            default = param.default
            info = default if isinstance(default, OptionInfo) else OptionInfo(default=default, param_decls=[])
            option_info[param_name] = info
            decls = info.param_decls or [f"--{param_name.replace('_', '-')}"]
            for decl in decls:
                option_map[decl] = param_name
            if info.default is not inspect._empty and info.default is not Ellipsis:
                values[param_name] = info.default

        idx = 1
        while idx < len(args):
            arg = args[idx]
            if not arg.startswith("--"):
                raise BadParameter(f"Unexpected argument: {arg}")
            if arg not in option_map:
                raise BadParameter(f"Unknown option: {arg}")
            param_name = option_map[arg]
            param = params[param_name]
            annotation = type_hints.get(param_name, param.annotation)
            info = option_info[param_name]

            if _is_bool_flag(annotation, info, arg):
                values[param_name] = not arg.startswith("--no-")
                idx += 1
                continue

            if idx + 1 >= len(args):
                raise BadParameter(f"Missing value for {arg}")
            raw = args[idx + 1]
            value = _coerce(raw, annotation)
            _validate_option(param_name, info, value)
            values[param_name] = value
            idx += 2

        for param_name, param in params.items():
            info = option_info[param_name]
            if info.default is Ellipsis and param_name not in values:
                raise BadParameter(f"Missing required option: {param_name}")

        try:
            func(**values)
        except BadParameter:
            raise

    def __call__(self, *args: Any, **kwargs: Any) -> None:
        if args:
            self._invoke(list(args))
            return
        try:
            self._invoke(sys.argv[1:])
        except BadParameter as exc:
            print(str(exc), file=sys.stderr)
            raise SystemExit(2)


def _is_bool_flag(annotation: Any, info: OptionInfo, arg: str) -> bool:
    if annotation is bool:
        return True
    if arg.startswith("--no-"):
        return True
    return False


def _coerce(value: str, annotation: Any) -> Any:
    if annotation is inspect._empty:
        return value
    origin = get_origin(annotation)
    if origin is None:
        if annotation is int:
            return int(value)
        if annotation is float:
            return float(value)
        if annotation is Path:
            return Path(value)
        if annotation is bool:
            return value.lower() in {"1", "true", "yes"}
        return value
    if origin in {list, List}:
        return value
    if origin in {types.UnionType, Union}:
        args = get_args(annotation)
        for arg in args:
            if arg is Path:
                return Path(value)
            if arg is int:
                return int(value)
        return value
    return value


def _validate_option(name: str, info: OptionInfo, value: Any) -> None:
    if value is None:
        return
    if info.min is not None and isinstance(value, (int, float)):
        if value < info.min:
            raise BadParameter(f"{name} must be >= {info.min}")
    if isinstance(value, Path):
        if info.exists and not value.exists():
            raise BadParameter(f"{value} does not exist")
        if info.dir_okay is False and value.is_dir():
            raise BadParameter(f"{value} must be a file")
        if info.readable and not os.access(value, os.R_OK):
            raise BadParameter(f"{value} is not readable")
