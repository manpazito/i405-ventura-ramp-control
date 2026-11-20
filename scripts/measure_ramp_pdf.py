"""Measure the hairpin loop and the meter stop line from the sketch PDF's linework.

The JSON export of the AutoCAD sketch drops the loop arcs and the red meter line; the
PDF plot keeps them as vector paths. This fits the PDF-to-drawing transform on the
up-leg edges (2C8, 2CC), then reports arc lengths and the stop-line station in meters
and writes data/interim/ramp_geometry/pdf_measurements.json. Sketch accuracy applies.

    uv run --with pymupdf python scripts/measure_ramp_pdf.py
"""

import json
from pathlib import Path

import numpy as np
import pymupdf

PDF = Path("data/ramp_geometry/i405_onramp.pdf")
SOURCE = Path("data/ramp_geometry/i405sb_geometry.json")
OUT = Path("data/interim/ramp_geometry/pdf_measurements.json")
YELLOW, RED = (1.0, 1.0, 0.0), (1.0, 0.0, 0.0)


def points(drawing: dict) -> np.ndarray:
    out: list = []
    for item in drawing["items"]:
        if item[0] == "l":
            new = [(q.x, q.y) for q in item[1:3]]
        else:  # cubic Bezier
            p = [np.array((q.x, q.y)) for q in item[1:5]]
            t = np.linspace(0, 1, 65)[:, None]
            new = (
                (1 - t) ** 3 * p[0]
                + 3 * (1 - t) ** 2 * t * p[1]
                + 3 * (1 - t) * t**2 * p[2]
                + t**3 * p[3]
            )
        out.extend(q for q in new if not out or not np.allclose(out[-1], q, atol=1e-9))
    return np.array(out)


def length(p: np.ndarray) -> float:
    return float(np.linalg.norm(np.diff(p, axis=0), axis=1).sum())


def station(line: np.ndarray, point: np.ndarray) -> float:
    """Distance along `line` to the point on it nearest to `point`."""
    best, s = (np.inf, 0.0), 0.0
    for a, b in zip(line, line[1:]):
        d = b - a
        t = np.clip(np.dot(point - a, d) / np.dot(d, d), 0, 1)
        gap = np.linalg.norm(point - (a + t * d))
        if gap < best[0]:
            best = (gap, s + t * np.linalg.norm(d))
        s += np.linalg.norm(d)
    return float(best[1])


def main() -> None:
    drawings = pymupdf.open(PDF)[0].get_drawings()
    color = lambda d: tuple(round(c, 2) for c in d.get("color") or ())  # noqa: E731
    yellow = [points(d) for d in drawings if color(d) == YELLOW]
    red = [points(d) for d in drawings if color(d) == RED]
    assert len(yellow) == 13 and len(red) == 1, "PDF linework changed; re-map paths"
    seg = {
        s["id"]: np.array(s["vertices_in"]) * 0.0254
        for s in json.loads(SOURCE.read_text())["segments"]
    }
    # Similarity transform with reflection (PDF y points down), fitted on 2C8 and 2CC.
    z = np.conj(np.vstack([yellow[0], yellow[3]]) @ [1, 1j])
    target = np.vstack([seg["2C8"], seg["2CC"]]) @ [1, 1j]
    coef, *_ = np.linalg.lstsq(np.c_[z, np.ones(len(z))], target, rcond=None)
    fit_error = float(np.abs(np.c_[z, np.ones(len(z))] @ coef - target).max())
    assert fit_error < 0.1, f"PDF does not match the JSON ({fit_error:.2f} m)"

    def to_m(p: np.ndarray) -> np.ndarray:
        w = coef[0] * np.conj(p @ [1, 1j]) + coef[1]
        return np.c_[w.real, w.imag]

    outer, inner = to_m(yellow[1]), np.vstack([to_m(yellow[i]) for i in (6, 5, 4)])
    line1, line2, stop = to_m(yellow[9]), to_m(yellow[12]), to_m(red[0])
    arcs = [length(p) for p in (outer, line1, line2, inner)]
    result = {
        "origin": "derived",
        "source_files": [str(PDF), str(SOURCE)],
        "fit_max_error_m": round(fit_error, 3),
        "loop_arc_m": dict(
            zip(("outer_edge", "lane_line_1", "lane_line_2", "inner_edge"), arcs)
        ),
        "loop_lane_centerline_m": [(a + b) / 2 for a, b in zip(arcs, arcs[1:])],
        "meter_line_width_m": length(stop),
        "meter_line_station_m": {
            k: station(seg[k], stop.mean(axis=0)) for k in ("2C8", "2EA", "2ED", "2CC")
        },
        "loop_vertices_m": {
            k: np.round(p, 3).tolist()
            for k, p in zip(
                ("outer_edge", "lane_line_1", "lane_line_2", "inner_edge"),
                (outer, line1, line2, inner),
            )
        },
        "meter_line_vertices_m": np.round(stop, 3).tolist(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=1))
    for key in (
        "fit_max_error_m",
        "loop_arc_m",
        "loop_lane_centerline_m",
        "meter_line_width_m",
        "meter_line_station_m",
    ):
        print(key, json.dumps(result[key], default=lambda v: round(v, 2)))


if __name__ == "__main__":
    main()
