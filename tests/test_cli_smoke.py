from pathlib import Path
import tempfile

from biopath.cli import solve


def test_cli_solve_smoke():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        out_png = tmp_path / "out.png"
        out_json = tmp_path / "out.json"
        out_report = tmp_path / "report.md"

        solve(
            map=Path("tests/fixtures/warehouse.json"),
            k=3,
            out=out_png,
            out_json=out_json,
            report=out_report,
            candidate_rule="all_walkable",
            min_wall_neighbors=1,
            local_improve=False,
            objective="mean",
            coverage_radius_m=None,
        )

        assert out_png.exists()
        assert out_json.exists()
        assert out_report.exists()
