"""Minimal PEP 517/660 backend to support offline editable installs."""

from __future__ import annotations

import base64
import hashlib
import os
import tarfile
import time
import zipfile
from pathlib import Path

NAME = "biopath"
VERSION = "0.1.0"
SUMMARY = "BioPath MVP: trap placement optimization on grid maps."
REQUIRES_PYTHON = ">=3.10"
REQUIRES_DIST = []
ENTRY_POINTS = "[console_scripts]\nbiopath=biopath.cli:app\n"


def _normalize_name(name: str) -> str:
    return name.replace("-", "_")


def _dist_info_dir() -> str:
    return f"{_normalize_name(NAME)}-{VERSION}.dist-info"


def _metadata() -> str:
    lines = [
        "Metadata-Version: 2.1",
        f"Name: {NAME}",
        f"Version: {VERSION}",
        f"Summary: {SUMMARY}",
        f"Requires-Python: {REQUIRES_PYTHON}",
    ]
    for req in REQUIRES_DIST:
        lines.append(f"Requires-Dist: {req}")
    return "\n".join(lines) + "\n"


def _wheel_metadata() -> str:
    return "\n".join(
        [
            "Wheel-Version: 1.0",
            "Generator: biopath-build-backend",
            "Root-Is-Purelib: true",
            "Tag: py3-none-any",
            "",
        ]
    )


def _hash_bytes(data: bytes) -> str:
    digest = hashlib.sha256(data).digest()
    b64 = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"sha256={b64}"


def _build_wheel(wheel_directory: str, editable: bool) -> str:
    wheel_directory = Path(wheel_directory)
    wheel_directory.mkdir(parents=True, exist_ok=True)

    dist_info = _dist_info_dir()
    wheel_name = f"{_normalize_name(NAME)}-{VERSION}-py3-none-any.whl"
    wheel_path = wheel_directory / wheel_name

    project_root = Path(os.getcwd()).resolve()
    pth_content = str(project_root)

    files = {
        f"{dist_info}/METADATA": _metadata().encode("utf-8"),
        f"{dist_info}/WHEEL": _wheel_metadata().encode("utf-8"),
        f"{dist_info}/entry_points.txt": ENTRY_POINTS.encode("utf-8"),
        f"{NAME}.pth": pth_content.encode("utf-8"),
    }

    record_lines = []
    with zipfile.ZipFile(wheel_path, "w", compression=zipfile.ZIP_DEFLATED) as wheel:
        for path, data in files.items():
            wheel.writestr(path, data)
            record_lines.append(
                f"{path},{_hash_bytes(data)},{len(data)}"
            )
        record_lines.append(f"{dist_info}/RECORD,,")
        record_content = "\n".join(record_lines) + "\n"
        wheel.writestr(f"{dist_info}/RECORD", record_content)

    return wheel_name


def build_wheel(wheel_directory: str, config_settings=None, metadata_directory=None) -> str:
    return _build_wheel(wheel_directory, editable=False)


def build_editable(wheel_directory: str, config_settings=None, metadata_directory=None) -> str:
    return _build_wheel(wheel_directory, editable=True)


def get_requires_for_build_wheel(config_settings=None):
    return []


def get_requires_for_build_editable(config_settings=None):
    return []


def prepare_metadata_for_build_wheel(metadata_directory, config_settings=None):
    metadata_directory = Path(metadata_directory)
    metadata_directory.mkdir(parents=True, exist_ok=True)
    dist_info = metadata_directory / _dist_info_dir()
    dist_info.mkdir(parents=True, exist_ok=True)
    (dist_info / "METADATA").write_text(_metadata(), encoding="utf-8")
    return str(dist_info.name)


def build_sdist(sdist_directory: str, config_settings=None) -> str:
    sdist_directory = Path(sdist_directory)
    sdist_directory.mkdir(parents=True, exist_ok=True)
    sdist_name = f"{_normalize_name(NAME)}-{VERSION}.tar.gz"
    sdist_path = sdist_directory / sdist_name

    root = Path(os.getcwd()).resolve()
    with tarfile.open(sdist_path, "w:gz") as tar:
        for path in root.rglob("*"):
            if ".git" in path.parts or "__pycache__" in path.parts:
                continue
            tar.add(path, arcname=f"{_normalize_name(NAME)}-{VERSION}/{path.relative_to(root)}")
    return sdist_name
