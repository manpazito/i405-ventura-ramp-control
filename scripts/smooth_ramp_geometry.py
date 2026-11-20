"""Smooth the hand-traced I-405 SB ramp sketch into SI polylines (derived data).

Reads data/ramp_geometry/i405sb_geometry.json (left unchanged), joins pieces that
share an endpoint, fits a smoothing spline per chain that stays within TOL_M of the
traced line with exact endpoints, and writes meters to data/interim/ramp_geometry/.
Gaps in the trace (the hairpin loop, downstream lane lines) are not filled.

    uv run python scripts/smooth_ramp_geometry.py
"""

import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from scipy.interpolate import splev, splprep  # noqa: E402
from scipy.spatial import cKDTree  # noqa: E402

SOURCE = Path("data/ramp_geometry/i405sb_geometry.json")
OUT = Path("data/interim/ramp_geometry")
INCH_M = 0.0254
TOL_M = 0.25  # allowed RMS departure from the trace; well under a 3.6 m lane
STEP_M = 1.0  # output vertex spacing


def densify(p: np.ndarray, step: float) -> np.ndarray:
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))]
    t = np.linspace(0, s[-1], max(int(s[-1] / step) + 1, 4))
    return np.c_[np.interp(t, s, p[:, 0]), np.interp(t, s, p[:, 1])]


def chains(segments: list[dict]) -> list[list[dict]]:
    """Join pieces end-to-start only where exactly two pieces meet (not at the gore)."""
    key = lambda xy: tuple(np.round(xy, 2))  # noqa: E731
    ends: dict = {}
    for s in segments:
        for xy in (s["vertices_in"][0], s["vertices_in"][-1]):
            ends[key(xy)] = ends.get(key(xy), 0) + 1
    starts = {key(s["vertices_in"][0]): s for s in segments}
    # Same role only: the ramp edge meeting the freeway edge at the taper end is a
    # real change of line, and each output polyline carries exactly one role.
    nexts = {
        id(s): n
        for s in segments
        if ends[key(s["vertices_in"][-1])] == 2
        and (n := starts.get(key(s["vertices_in"][-1]))) is not None
        and n["role"] == s["role"]
    }
    followers = {id(n) for n in nexts.values() if n is not None}
    out = []
    for s in segments:
        if id(s) in followers:
            continue
        chain = [s]
        while nexts.get(id(chain[-1])) is not None:
            chain.append(nexts[id(chain[-1])])
        out.append(chain)
    assert sum(map(len, out)) == len(segments), "closed ring of pieces dropped"
    return out


def smooth(p: np.ndarray) -> tuple[np.ndarray, float]:
    dense = densify(p, 0.5)
    w = np.ones(len(dense))
    w[[0, -1]] = 1e3
    tck, _ = splprep(dense.T, w=w, s=len(dense) * TOL_M**2, k=3)
    fine = np.array(splev(np.linspace(0, 1, 20 * len(dense)), tck)).T
    fine[0], fine[-1] = p[0], p[-1]
    deviation = float(cKDTree(fine).query(dense)[0].max())
    return densify(fine, STEP_M), deviation


def main() -> None:
    raw = SOURCE.read_bytes()
    src = json.loads(raw)
    OUT.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 14))
    result = []
    for chain in chains(src["segments"]):
        traced = np.vstack(
            [np.array(c["vertices_in"]) * INCH_M for c in chain]
        )  # duplicate joint vertices are harmless after densify
        traced = traced[
            np.r_[True, np.linalg.norm(np.diff(traced, axis=0), axis=1) > 1e-6]
        ]
        smoothed, dev = smooth(traced)
        kept = dev > 4 * TOL_M  # a real sharp corner (gore tip): keep the trace
        if kept:
            smoothed, dev = densify(traced, STEP_M), 0.0
        assert np.allclose(smoothed[[0, -1]], traced[[0, -1]]), "endpoints moved"
        length = float(np.linalg.norm(np.diff(smoothed, axis=0), axis=1).sum())
        result.append(
            {
                "source_ids": [c["id"] for c in chain],
                "role": chain[0]["role"],
                "length_m": round(length, 2),
                "max_departure_from_trace_m": round(dev, 3),
                "kept_as_traced": bool(kept),
                "vertices_m": np.round(smoothed, 3).tolist(),
            }
        )
        ax.plot(*traced.T, color="#c0392b", lw=0.8)
        ax.plot(*smoothed.T, color="#1f6feb", lw=0.8)
    ax.set_aspect("equal")
    ax.set(
        xlabel="x (m, local drawing frame)",
        ylabel="y (m)",
        title="Red: traced sketch, blue: smoothed",
    )
    fig.tight_layout()
    fig.savefig(OUT / "i405sb_geometry_smoothed.png", dpi=160)
    payload = {
        "origin": "derived",
        "source_file": str(SOURCE),
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "units": "meters",
        "frame": "local AutoCAD drawing frame scaled from inches; not georeferenced",
        "method": f"cubic smoothing spline per joined chain, RMS tolerance {TOL_M} m, "
        f"endpoints fixed, resampled every {STEP_M} m",
        "not_filled": [
            "hairpin loop between the up leg (2C8/2CC) and return leg (2CB/2D0)",
            "mainline lane lines west of 376 downstream of the acceleration lane",
        ],
        "polylines": result,
    }
    (OUT / "i405sb_geometry_smoothed.json").write_text(json.dumps(payload, indent=1))
    for r in result:
        print(
            f"{'+'.join(r['source_ids']):12} {r['role']:22} {r['length_m']:7.1f} m"
            f"  max departure {r['max_departure_from_trace_m']:.2f} m"
        )


if __name__ == "__main__":
    main()
