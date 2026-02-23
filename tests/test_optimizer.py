from pathlib import Path

from math import isclose

from biopath.candidates import all_walkable
from biopath.mapio import load_map
from biopath.optimizer import greedy_optimize


def test_greedy_optimize_center():
    grid_map = load_map(Path("tests/fixtures/simple_room.json"))
    candidates = all_walkable(grid_map)
    traps, objective = greedy_optimize(grid_map, candidates, k=1)

    assert traps == [(2, 2)]
    assert isclose(objective, 4.0 / 3.0, rel_tol=1e-6)
