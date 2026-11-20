"""Live demo: run the I-405 SB Ventura on-ramp model and watch it in a browser.

    uv run python scripts/live_demo.py            # then open http://localhost:8405

Runs the same engine and demand as `arm-ablation` (configs/i405.yaml): one demand case,
two metering rules side by side, one seed. Each 5-hour run takes about 30 s, and the
two rules run in parallel. The 0.9× case is started at launch so the page opens ready.
Simulated and uncalibrated, like every result in the deck.
"""

import argparse
import json
import os
from concurrent.futures import ProcessPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from urllib.parse import parse_qs, urlparse

import yaml

from adaptive_ramp_metering.simulation import ablation, micro

PORT = 8405
PAGE = Path(__file__).with_name("live_demo.html")
SNAPSHOT_S = 5  # one animation frame per 5 simulated seconds
DEFAULT = ("x0.9", ("none", "alinea"), 1)


class StreetTraced(micro.Simulation):
    """Also records the vehicles waiting on Ventura Blvd (outside the modeled ramp)."""

    def step(self) -> None:
        super().step()
        if (
            self.trace is not None
            and self.index % round(self.cfg["snapshot_interval_s"] / self.h) == 0
        ):
            self.trace.setdefault("street", []).append(int(self.waiting[0]))


def run_case(sim_cfg: dict, case: str, controller: str, seed: int, rule: dict) -> dict:
    scenario = next(s for s in sim_cfg["scenarios"] if s["id"] == case)
    run = StreetTraced(sim_cfg, scenario, controller, seed, trace=True).run()
    tr, m = run["trace"], run["metrics"]
    frames = [[] for _ in tr["queue"]]
    lane = {ln["id"]: k for k, ln in enumerate(micro.build_lanes(sim_cfg)[0])}
    for t, _vid, lane_id, x, v, _acc in tr["states"]:
        frames[round(t / sim_cfg["snapshot_interval_s"]) - 1] += [
            lane[lane_id],
            round(x, 1),
            round(v, 1),
        ]
    requested = m["requested_ramp_veh"] + m["requested_mainline_veh"]
    return {
        "frames": frames,
        "ramp_queue": [q[1] for q in tr["queue"]],
        "rate_vph": [None if q[4] is None else round(3600 * q[4]) for q in tr["queue"]],
        "street": tr["street"],
        "detector": [
            [o["interval_end_s"], o["mean_speed_mps"]]
            for o in run["observations"]
            if o["sensor_id"] == "mainline_upstream"
        ],
        "summary": {
            "congested_min": ablation.persistent_minutes(
                run["observations"], "mainline_upstream", rule
            ),
            "street_max_veh": m["boundary_ramp_max_veh"],
            "served_pct": 100 * m["exited_veh"] / requested,
            "time_per_veh_min": m["total_time_veh_s"] / requested / 60,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/i405.yaml"))
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()
    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    sim_cfg = ablation.build_config(cfg, ablation.historical_profile(cfg["demand"]))
    sim_cfg["snapshot_interval_s"] = SNAPSHOT_S
    rule = cfg["ablation"]["congestion"]
    lanes, ends = micro.build_lanes(sim_cfg)
    det = sim_cfg["detectors"]
    meta = {
        "cases": [v["id"] for v in cfg["ablation"]["variants"]],
        "controllers": cfg["ablation"]["controllers"],
        "seeds": sim_cfg["seeds"],
        "default": {"case": DEFAULT[0], "controllers": DEFAULT[1], "seed": DEFAULT[2]},
        "start": cfg["demand"]["start"],
        "duration_s": sim_cfg["duration_s"],
        "snapshot_s": SNAPSHOT_S,
        "lanes": lanes,
        "merge_m": ends[-1],
        "stop_line_m": sim_cfg["meter"]["stop_line_m"],
        "detectors": {
            "mainline upstream": ends[-1] + det["mainline_upstream_m"],
            "merge area": ends[-1] + det["merge_area_m"],
        },
        "speed_line_mps": rule["speed_below_mps"],
    }
    pool = ProcessPoolExecutor(min(4, os.cpu_count() or 1))
    jobs, lock = {}, Lock()

    def job(case: str, controller: str, seed: int):
        with lock:  # one simulation per key, shared by every request that asks for it
            key = (case, controller, seed)
            if key not in jobs:
                jobs[key] = pool.submit(run_case, sim_cfg, *key, rule)
            return jobs[key]

    for controller in DEFAULT[1]:
        job(DEFAULT[0], controller, DEFAULT[2])

    class Handler(BaseHTTPRequestHandler):
        def send(self, body: bytes, kind: str, status: int = 200) -> None:
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            url = urlparse(self.path)
            if url.path == "/":
                return self.send(PAGE.read_bytes(), "text/html; charset=utf-8")
            if url.path == "/meta":
                return self.send(json.dumps(meta).encode(), "application/json")
            if url.path == "/run":
                q = {k: v[0] for k, v in parse_qs(url.query).items()}
                try:
                    seed = int(q.get("seed", ""))
                except ValueError:
                    seed = None
                if (
                    q.get("case") not in meta["cases"]
                    or q.get("controller") not in meta["controllers"]
                    or seed not in meta["seeds"]
                ):
                    return self.send(
                        b"unknown case, controller or seed", "text/plain", 400
                    )
                body = json.dumps(job(q["case"], q["controller"], seed).result())
                return self.send(body.encode(), "application/json")
            self.send(b"not found", "text/plain", 404)

        def log_message(self, *_args) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(
        f"Live demo on http://localhost:{args.port}  (VS Code: Ports > Forward a Port > {args.port})"
    )
    print(
        f"Pre-running {DEFAULT[0]}: {' vs '.join(DEFAULT[1])}, seed {DEFAULT[2]} (about 30 s)"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        pool.shutdown(cancel_futures=True)


if __name__ == "__main__":
    main()
