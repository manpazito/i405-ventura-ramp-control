"""Bounded ramp-meter decision rules; see docs/mathematical_model/ramp_metering.md."""

import math


def decide(
    ctrl: dict,
    mode: str,
    time_s: float,
    rate: float | None,
    observation: dict | None,
    queue_estimate_veh: float,
    ramp_demand_veh_per_s: float | None,
    last_valid_time_s: float | None,
    step_s: float,
    queue_occupancy: float | None = None,
) -> dict:
    """Return one control-command record from measurements only.

    `rate` is the currently applied command (None at startup); `observation` is the
    latest completed downstream detector record or None; `ramp_demand_veh_per_s` is the
    latest valid entrance-detector flow or None. ALINEA integrates from the
    applied, bounded rate so saturation and overrides do not wind up the recurrence.
    Mode "caltrans" is the local traffic-responsive plan with queue override
    (docs/i405_ablation.md); `queue_occupancy` is the ramp queue detector's latest value.
    """
    lo, hi = ctrl["min_rate_veh_per_s"], ctrl["max_rate_veh_per_s"]
    fixed = ctrl["fixed_rate_veh_per_s"]
    occupancy = observation["occupancy_fraction"] if observation else None
    fallback = "nominal"
    if mode == "fixed":
        value, reason = fixed, "fixed_rate"
    elif rate is None:
        value, reason = fixed, "startup_fixed_rate"
    elif occupancy is None:
        if (
            last_valid_time_s is not None
            and time_s - last_valid_time_s <= ctrl["fault_hold_s"]
        ):
            value, reason, fallback = rate, "hold_last_valid_command", "hold"
        else:
            value, reason, fallback = fixed, "fixed_rate_fallback", "fallback"
    elif mode == "caltrans":
        # Stepwise plan: the rate of the highest level whose occupancy threshold is met.
        plan = ctrl["caltrans"]
        lanes, top = plan["metered_lanes"], plan["levels"] - 1
        (o_first, o_last), (r_first, r_last) = (
            plan["occupancy"],
            plan["rate_veh_per_h_per_lane"],
        )
        level = math.floor((occupancy - o_first) / (o_last - o_first) * top)
        level = min(top, max(0, level))
        value = lanes * (r_first + level * (r_last - r_first) / top) / 3600
        reason = "plan_rate"
        # Queue override: step up from the applied rate while the queue loop is covered;
        # back to the plan rate in one step once it clears.
        if queue_occupancy is not None and queue_occupancy >= plan["queue_occupancy"]:
            value = (
                max(value, rate) + lanes * plan["queue_step_veh_per_h_per_lane"] / 3600
            )
            reason = "queue_override"
    else:
        alinea = ctrl["alinea"]
        value = rate + alinea["gain_veh_per_s_per_occupancy"] * (
            alinea["target_occupancy"] - occupancy
        )
        reason = "alinea"
        # ALINEA/Q queue control (Smaragdis & Papageorgiou 2003): the release rate that
        # returns the estimated queue to its target within one interval given measured
        # ramp demand; the larger of the two rates applies.
        if ramp_demand_veh_per_s is not None:
            relief = (queue_estimate_veh - ctrl["queue_target_veh"]) / ctrl[
                "interval_s"
            ] + ramp_demand_veh_per_s
            if relief > value:
                value, reason = relief, "queue_control"
    return {
        "issue_time_s": time_s,
        "apply_time_s": time_s + step_s,
        "actuator_id": "ramp_meter",
        "action": "set_release_rate",
        "value": min(hi, max(lo, value)),
        "units": "veh/s",
        "min_value": lo,
        "max_value": hi,
        "fallback_state": fallback,
        "reason": reason,
        "occupancy_fraction": occupancy,
        "observation_end_s": observation["interval_end_s"] if observation else None,
        "queue_estimate_veh": queue_estimate_veh,
        "queue_occupancy_fraction": queue_occupancy,
        "ramp_demand_veh_per_s": ramp_demand_veh_per_s,
    }
