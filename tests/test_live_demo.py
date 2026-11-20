"""The live demo's animation traces line up frame by frame (synthetic config)."""

import importlib.util
from pathlib import Path

import yaml

spec = importlib.util.spec_from_file_location("live_demo", "scripts/live_demo.py")
live_demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(live_demo)


def test_every_trace_has_one_entry_per_frame():
    cfg = yaml.safe_load(Path("configs/micro.yaml").read_text())
    cfg["duration_s"], cfg["snapshot_interval_s"] = 300, 2
    cfg["scenarios"] = [
        {
            "id": "test",
            "name": "Test",
            "description": "Synthetic test",
            # ramp demand above the meter's rate so vehicles wait on the street
            "periods": [
                {"until_s": 300, "ramp_veh_per_s": 0.8, "mainline_veh_per_s": 0.3}
            ],
        }
    ]
    rule = {"speed_below_mps": 20, "occupancy_above": 0.26, "min_intervals": 10}
    run = live_demo.run_case(cfg, "test", "fixed", 1, rule)
    n = 300 // 2
    assert len(run["frames"]) == len(run["street"]) == len(run["ramp_queue"]) == n
    assert all(len(f) % 3 == 0 for f in run["frames"])
    assert max(run["street"]) > 0
