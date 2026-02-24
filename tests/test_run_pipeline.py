from biopath.capture import CaptureEstimate, RobustCaptureEstimate
from biopath.run_pipeline import SolveOptions, run_solve


def _tiny_map() -> dict:
    return {
        "name": "Tiny",
        "cell_size_m": 1.0,
        "ascii": [
            "#####",
            "#...#",
            "#####",
        ],
    }


def _fake_robust(*args, **kwargs) -> RobustCaptureEstimate:
    return RobustCaptureEstimate(
        robust_score=0.42,
        scenario_scores=[
            {
                "name": "lazy_neutral",
                "capture_probability": 0.77,
                "expected_time_to_capture": 7.0,
                "ci95_low": 0.70,
                "ci95_high": 0.84,
            },
            {
                "name": "biased_right",
                "capture_probability": 0.81,
                "expected_time_to_capture": 6.5,
                "ci95_low": 0.73,
                "ci95_high": 0.89,
            },
            {
                "name": "biased_down",
                "capture_probability": 0.75,
                "expected_time_to_capture": 7.2,
                "ci95_low": 0.67,
                "ci95_high": 0.83,
            },
        ],
    )


def test_run_solve_robust_lazy_reuses_lazy_scenario_capture():
    import biopath.run_pipeline as rp

    simulate_called = False

    def _fake_simulate(*args, **kwargs):
        nonlocal simulate_called
        simulate_called = True
        return CaptureEstimate(0.1, 10.0, 0.0, 0.2)

    old_robust = rp.robust_capture_score
    old_sim = rp.simulate_capture_probability
    rp.robust_capture_score = _fake_robust
    rp.simulate_capture_probability = _fake_simulate
    try:
        result = run_solve(
            _tiny_map(),
            runs_root="runs",
            options=SolveOptions(
                k=1,
                objective="robust_capture",
                local_improve=False,
                movement_model="lazy",
                create_run=False,
            ),
        )
    finally:
        rp.robust_capture_score = old_robust
        rp.simulate_capture_probability = old_sim

    assert simulate_called is False
    assert result["capture_probability"] == 0.77
    assert result["expected_time_to_capture"] == 7.0
    assert result["ci95_low"] == 0.70
    assert result["ci95_high"] == 0.84


def test_run_solve_robust_non_lazy_reuses_primary_scenario_capture():
    import biopath.run_pipeline as rp

    simulate_called = False

    def _fake_simulate(*args, **kwargs):
        nonlocal simulate_called
        simulate_called = True
        return CaptureEstimate(0.33, 8.0, 0.20, 0.46)

    def _fake_robust_unbiased(*args, **kwargs) -> RobustCaptureEstimate:
        return RobustCaptureEstimate(
            robust_score=0.39,
            scenario_scores=[
                {
                    "name": "unbiased_neutral",
                    "capture_probability": 0.61,
                    "expected_time_to_capture": 6.9,
                    "ci95_low": 0.53,
                    "ci95_high": 0.69,
                },
                {
                    "name": "biased_right",
                    "capture_probability": 0.68,
                    "expected_time_to_capture": 6.2,
                    "ci95_low": 0.60,
                    "ci95_high": 0.76,
                },
                {
                    "name": "biased_down",
                    "capture_probability": 0.39,
                    "expected_time_to_capture": 8.1,
                    "ci95_low": 0.31,
                    "ci95_high": 0.47,
                },
            ],
        )

    old_robust = rp.robust_capture_score
    old_sim = rp.simulate_capture_probability
    rp.robust_capture_score = _fake_robust_unbiased
    rp.simulate_capture_probability = _fake_simulate
    try:
        result = run_solve(
            _tiny_map(),
            runs_root="runs",
            options=SolveOptions(
                k=1,
                objective="robust_capture",
                local_improve=False,
                movement_model="unbiased",
                create_run=False,
            ),
        )
    finally:
        rp.robust_capture_score = old_robust
        rp.simulate_capture_probability = old_sim

    assert simulate_called is False
    assert result["capture_probability"] == 0.61
