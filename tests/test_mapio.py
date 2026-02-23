from pathlib import Path

from biopath.mapio import load_map


def test_load_map_simple_room():
    path = Path("tests/fixtures/simple_room.json")
    grid_map = load_map(path)

    assert grid_map.name == "Simple Room"
    assert grid_map.cell_size_m == 1.0
    assert grid_map.height == 5
    assert grid_map.width == 5
    assert grid_map.walkable_count == 9
    assert grid_map.is_walkable(2, 2)
    assert not grid_map.is_walkable(0, 0)


def test_load_map_with_weights():
    path = Path("tests/fixtures/weighted_room.json")
    grid_map = load_map(path)

    assert grid_map.weights_provided
    assert grid_map.weight_total == 13.0
    assert grid_map.weights[2][2] == 5.0
    assert grid_map.weights[0][0] == 0.0
