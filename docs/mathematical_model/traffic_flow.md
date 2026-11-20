# Traffic flow foundation

Status: analytical background; the triangular diagram and a finite-volume CTM
are implemented only in the synthetic demo, without calibration or
selection of the final course model. Definitions follow the framework in
[Treiber and Kesting, Traffic Flow Dynamics](https://doi.org/10.1007/978-3-642-32460-4).

## Flow, density, and speed

For a declared lane or lane group, flow $q$ is crossings per second, density
$k$ is vehicles per meter, and $v$ is space-mean speed in m/s. Their fundamental
relation is

$$
q=kv.
$$

This needs consistent space-time aggregation. A detector's arithmetic average of
passing speeds is a time-mean speed and cannot generally be substituted for a
space-mean speed. For heterogeneous lanes, sum lane flows and densities and derive
the corresponding density-weighted speed. Record the speed definition in exports.

Microscopic models evolve each vehicle's position and speed. Macroscopic models
evolve aggregate density and flow. A car-following model alone does not specify
merging, lane changes, network boundaries, or signal service. Aggregate data may
constrain flow patterns without identifying unique microscopic parameters.

## Conservation

For a fixed road section $[x_a,x_b]$, with no internal sources,

$$
\frac{d}{d\tau}\int_{x_a}^{x_b}k(x,\tau)\,dx
=q(x_a,\tau)-q(x_b,\tau).
$$

With distributed arrivals and exits $s_{\rm in},s_{\rm out}$ in veh/(m s),

$$
\frac{\partial k}{\partial\tau}+\frac{\partial q}{\partial x}
=s_{\rm in}-s_{\rm out}.
$$

A discrete section therefore has $N_{t+1}=N_t+I_t-O_t$, where $I_t,O_t$
are interval counts including ramp transfers. A merge departure is one vehicle
leaving the ramp and entering the mainline, not a second external arrival.

## Fundamental diagrams, demand, and supply

An equilibrium fundamental diagram $q=F(k)$ closes a first-order macroscopic
description. A triangular diagram is a candidate analytical comparator:

$$
F(k)=\min\{v_fk,\ w(k_j-k)\},\qquad
k_c=\frac{wk_j}{v_f+w},\qquad C=v_fk_c,
$$

with $v_f,w>0$ and $0\le k\le k_j$. Here $w$ is a positive magnitude;
the congested branch has slope $-w$. Its sending demand and receiving supply are

$$
\mathcal D(k)=\min(v_fk,C),\qquad
\mathcal S(k)=\min(C,w(k_j-k)).
$$

At an ordinary interface, $q_{\rm transfer}=\min(\mathcal D_{\rm upstream},
\mathcal S_{\rm downstream})$. A merge additionally needs an explicit allocation
rule: total mainline plus ramp inflow cannot exceed downstream supply. These
concepts support a possible cell-transmission comparison; no such comparator has
been selected. See [Daganzo's network CTM report](https://escholarship.org/uc/item/9pz309w7).

Boundary requested demand differs from admitted flow and from a link's sending
function. Never treat constrained ramp discharge as unconstrained arrival demand.

## Bottlenecks and propagation

A bottleneck limits service through geometry, merging, or control. Demand above
available service accumulates vehicles. For two uniform states on either side of
a sharp front, conservation gives the shock speed

$$
c_{\rm shock}=\frac{q_2-q_1}{k_2-k_1}\quad\text{m/s},\qquad k_2\ne k_1.
$$

A negative speed means upstream propagation. This formula does not locate a
real queue without data and boundary conditions. A point queue tracks accumulation
but has no spatial propagation; spillback requires storage and upstream coupling.
An equilibrium diagram alone does not capture all hysteresis or capacity-drop
effects. Those mechanisms require separately justified models and evidence.

Candidate finite-volume schemes must satisfy their stability/CFL condition; for
the triangular diagram a necessary explicit step restriction is
$h\max(v_f,w)\le\Delta x$, where $\Delta x$ is cell length in meters.
This is separate from microscopic integration
accuracy. No numerical step, capacity, or diagram parameter is assigned here.
