from pathlib import Path

from math import isclose

from biopath.mapio import load_map
from biopath.objective import mean_distance_to_traps, weighted_mean_distance_to_traps


def test_mean_distance_center_trap():
    grid_map = load_map(Path("tests/fixtures/simple_room.json"))
    objective = mean_distance_to_traps(grid_map, [(2, 2)])
    assert isclose(objective, 4.0 / 3.0, rel_tol=1e-6)


def test_weighted_mean_distance_center_trap():
    grid_map = load_map(Path("tests/fixtures/weighted_room.json"))
    objective = weighted_mean_distance_to_traps(grid_map, [(2, 2)])
    assert isclose(objective, 12.0 / 13.0, rel_tol=1e-6)
