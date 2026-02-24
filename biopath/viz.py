"""Visualization helpers."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Iterable, List, Tuple

from .mapio import GridMap


def save_heatmap(
    grid_map: GridMap,
    distance_map: List[List[float | None]],
    traps: Iterable[Tuple[int, int]],
    out_path: str | Path,
) -> None:
    """Save a polished distance heatmap with trap overlay to a PNG file."""
    out_path = Path(out_path)

    try:
        import matplotlib  # type: ignore

        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        _save_heatmap_fallback(grid_map, distance_map, traps, out_path)
        return

    data = [[math.nan if value is None else value for value in row] for row in distance_map]
    cmap = plt.cm.viridis.copy()
    cmap.set_bad(color="#161a1d")

    fig, ax = plt.subplots(figsize=(9.4, 4.9), dpi=220)
    fig.patch.set_facecolor("#06130e")
    ax.set_facecolor("#071711")

    im = ax.imshow(data, cmap=cmap, origin="upper", interpolation="nearest")
    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label("Distance (m)", color="#d7ecdf", fontsize=8)
    cbar.ax.tick_params(labelsize=7, colors="#bfdacb")
    cbar.outline.set_edgecolor("#2a4a3a")

    traps_list = list(traps)
    if traps_list:
        rows, cols = zip(*traps_list)
        ax.scatter(cols, rows, c="#ffe9d4", s=34, marker="X", linewidths=0.8, edgecolors="#8a4330", label="Traps")
        leg = ax.legend(
            loc="upper right",
            frameon=True,
            fontsize=7.2,
            facecolor="#10241a",
            edgecolor="#2a4a3a",
            labelcolor="#eaf8f0",
        )
        for txt in leg.get_texts():
            txt.set_color("#eaf8f0")

    for spine in ax.spines.values():
        spine.set_color("#27463a")
        spine.set_linewidth(0.85)

    ax.set_xticks([])
    ax.set_yticks([])
    fig.tight_layout(pad=0.1)
    fig.savefig(out_path, dpi=220, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)


def _save_heatmap_fallback(
    grid_map: GridMap,
    distance_map: List[List[float | None]],
    traps: Iterable[Tuple[int, int]],
    out_path: Path,
) -> None:
    import zlib
    import struct

    height = grid_map.height
    width = grid_map.width
    traps_set = set(traps)

    finite_values = [
        value
        for row in distance_map
        for value in row
        if value is not None and not math.isinf(value)
    ]
    min_val = min(finite_values) if finite_values else 0.0
    max_val = max(finite_values) if finite_values else 1.0
    span = max(max_val - min_val, 1e-6)

    scale = 10
    pixels: List[List[Tuple[int, int, int]]] = []
    for row in range(height):
        for _ in range(scale):
            pixel_row: List[Tuple[int, int, int]] = []
            for col in range(width):
                if (row, col) in traps_set:
                    color = (231, 76, 60)
                else:
                    value = distance_map[row][col]
                    if value is None:
                        color = (26, 26, 26)
                    elif math.isinf(value):
                        color = (90, 90, 90)
                    else:
                        t = (value - min_val) / span
                        r = int(255 * t)
                        g = int(255 * t)
                        b = int(255 * (1 - t))
                        color = (r, g, b)
                pixel_row.extend([color] * scale)
            pixels.append(pixel_row)

    _write_png(out_path, pixels, width * scale, height * scale)


def _write_png(path: Path, pixels: List[List[Tuple[int, int, int]]], width: int, height: int) -> None:
    import zlib
    import struct

    def chunk(tag: bytes, data: bytes) -> bytes:
        length = struct.pack(">I", len(data))
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return length + tag + data + struct.pack(">I", crc)

    raw = bytearray()
    for row in pixels:
        raw.append(0)
        for r, g, b in row:
            raw.extend(bytes([r, g, b]))

    compressed = zlib.compress(bytes(raw))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    with open(path, "wb") as handle:
        handle.write(b"\x89PNG\r\n\x1a\n")
        handle.write(chunk(b"IHDR", header))
        handle.write(chunk(b"IDAT", compressed))
        handle.write(chunk(b"IEND", b""))
