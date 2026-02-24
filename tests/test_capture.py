from pathlib import Path

from biopath.capture import robust_capture_score, simulate_capture_probability
from biopath.mapio import load_map, load_map_data


def test_capture_probability_monotonic_for_superset_traps_with_fixed_seed():
    grid_map = load_map(Path("tests/fixtures/simple_room.json"))

    base = simulate_capture_probability(
        grid_map,
        [(2, 2)],
        mc_runs=180,
        time_horizon_steps=16,
        seed=17,
        movement_model="lazy",
    )
    superset = simulate_capture_probability(
        grid_map,
        [(2, 2), (1, 2)],
        mc_runs=180,
        time_horizon_steps=16,
        seed=17,
        movement_model="lazy",
    )

    assert superset.capture_probability >= base.capture_probability


def test_robust_capture_switches_to_sparse_stress_scenario_on_sparse_map():
    grid_map = load_map_data(
        {
            "name": "Sparse Snake",
            "cell_size_m": 1.0,
            "ascii": [
                "#########",
                "#.......#",
                "#######.#",
                "#.......#",
                "#.#######",
                "#.......#",
                "#########",
            ],
        }
    )

    robust = robust_capture_score(
        grid_map,
        [(1, 1), (3, 4)],
        mc_runs=80,
        time_horizon_steps=24,
        seed=5,
    )

    scenario_names = {str(s["name"]) for s in robust.scenario_scores}
    assert "sparse_stress" in scenario_names
    assert "biased_down" not in scenario_names


def test_robust_capture_keeps_directional_scenarios_on_dense_map():
    grid_map = load_map(Path("tests/fixtures/simple_room.json"))

    robust = robust_capture_score(
        grid_map,
        [(2, 2)],
        mc_runs=80,
        time_horizon_steps=24,
        seed=5,
    )

    scenario_names = {str(s["name"]) for s in robust.scenario_scores}
    assert "lazy_neutral" in scenario_names
    assert "biased_down" in scenario_names
    assert "sparse_stress" not in scenario_names


def test_robust_capture_uses_primary_movement_model_for_neutral_scenario():
    grid_map = load_map(Path("tests/fixtures/simple_room.json"))

    robust = robust_capture_score(
        grid_map,
        [(2, 2)],
        mc_runs=80,
        time_horizon_steps=24,
        seed=5,
        primary_movement_model="unbiased",
    )

    scenario_names = {str(s["name"]) for s in robust.scenario_scores}
    assert "unbiased_neutral" in scenario_names
    assert "lazy_neutral" not in scenario_names
