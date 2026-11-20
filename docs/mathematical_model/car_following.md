# Intelligent Driver Model: candidate formulation

Status: documented for assessment; not implemented, selected, or calibrated.
The original source is [Treiber, Hennecke, and Helbing (2000)](https://doi.org/10.1103/PhysRevE.62.1805).
Use the common bounded desired-gap form below; the original paper also discusses
a more general gap parameterization. Record the exact variant before implementation.

## Dynamics and sign convention

For follower $i$ with leader $i-1$, front-bumper coordinates increase downstream:

$$
\dot x_i=v_i,\quad
s_i=x_{i-1}-x_i-\ell_{i-1}>0,\quad
\Delta v_i=v_i-v_{i-1},\quad \dot s_i=-\Delta v_i.
$$

Positive $\Delta v_i$ means the follower is closing on the leader. The candidate
IDM law is

$$
\dot v_i=a\left[1-\left(\frac{v_i}{v_0}\right)^\delta
-\left(\frac{s^*(v_i,\Delta v_i)}{s_i}\right)^2\right],
$$

$$
s^*(v_i,\Delta v_i)=s_0+\max\left(0,v_iT+
\frac{v_i\Delta v_i}{2\sqrt{ab}}\right).
$$

| Quantity | Definition | Unit / domain |
| --- | --- | --- |
| $x_i,\ell_{i-1}$ | Follower front position, leader length | m; length positive |
| $v_i,v_{i-1}$ | Follower and leader speeds | m/s, nonnegative |
| $s_i,s^*$ | Actual net gap, desired dynamic gap | m |
| $\Delta v_i$ | Follower speed minus leader speed | m/s |
| $v_0$ | Desired free-road speed | m/s, positive |
| $a$ | Acceleration scale | m/s², positive |
| $b$ | Comfortable braking magnitude; not a hard braking limit | m/s², positive |
| $T$ | Desired time gap | s, positive |
| $s_0$ | Standstill net gap | m, positive |
| $\delta$ | Free-road acceleration exponent | dimensionless, positive |

The bracket is dimensionless; $v_i\Delta v_i/\sqrt{ab}$ has units of meters.
There are no numerical defaults in this repository.

## Analytical checks and stability

With no leader, use the free-road limit (interaction term zero). For equilibrium
following at a common speed $0\le v<v_0$, setting $\dot v=0$ gives

$$
s_{\rm eq}(v)=\frac{s_0+vT}{\sqrt{1-(v/v_0)^\delta}}.
$$

Thus $s_0+vT$ alone is not the exact finite-speed equilibrium gap. At rest the
equilibrium gap is $s_0$. These are analytical targets for future verification.

Stability is parameter- and operating-point-dependent. Local relaxation after a
disturbance and string stability (whether disturbances amplify along vehicles) are
different questions. Linearize around an equilibrium or run controlled perturbations
with step refinement before interpreting amplification as traffic instability.
No stability conclusion for the I-405 site follows from choosing IDM.

## Numerical implementation considerations

The [authors' numerical notes](https://traffic-simulation.de/info/info_IDM.html)
describe constant-acceleration ballistic integration. A candidate step is

$$
v_i^{n+1}=v_i^n+h\alpha_i^n,\qquad
x_i^{n+1}=x_i^n+h v_i^n+\tfrac12h^2\alpha_i^n,
$$

where $\alpha_i^n$ is acceleration evaluated from one common old state. If
$\alpha_i^n<0$ and stopping occurs within the step, use
$h_{\rm stop}=-v_i^n/\alpha_i^n$, advance only to that stopping point, and
hold speed at zero for the remainder. Clipping speed after a full ballistic
position step is inconsistent.

Future checks must reject invalid parameters and nonpositive gaps, resolve leader
and boundary events, count detector crossings between steps, and compare smaller
steps. A small denominator substitute can conceal collisions. Finite-step collision
freedom is not guaranteed by the continuous formula. Any acceleration cap or other
repair changes the effective model and needs documentation and verification.

The basic law assumes immediate response to the current leader and does not model
reaction delay, lane changing, merge priority, perception errors, or traffic-signal
logic. See the validation plan.

## Driver heterogeneity (optional)

The law above gives every driver the same parameters. The microscopic prototype
(`simulation/micro.py`, [design record](../micro_demo.md), decisions D018 and D019) can
give driver $i$ an own value of each parameter $\theta\in\{v_0,T,a,b,s_0\}$ and of the
merging safety limit $b_{\rm safe}$, drawn once when the vehicle is created and kept for
the whole trip. The driver has one percentile $u_{i\theta}\sim U(0,1)$ per parameter,
independent across drivers and parameters, and

$$
\theta_i=\bar\theta\,f_s(u_{i\theta};c_\theta),\qquad
\mathrm E[f_s]=1,\qquad \mathrm{sd}[f_s]=c_\theta ,
$$

where $\bar\theta$ is the fixed value, $c_\theta$ the configured coefficient of variation
(`vehicle.spread`; zero returns the fixed value) and $s$ the shape (`vehicle.shape`).
Every shape has exactly this mean and standard deviation, so two shapes with the same
$c_\theta$ differ only in symmetry and tails. With
$z(u)=\Phi^{-1}\bigl(p+(1-2p)u\bigr)$, $p=\Phi(-2)$, a standard normal truncated at two
standard deviations, whose standard deviation is $\kappa=0.8796$:

| Shape | $f_s(u;c)$ | Range of $f_s$ | Symmetry |
| --- | --- | --- | --- |
| `normal` | $1+c\,z(u)/\kappa$ | $1\pm2.274\,c$ | symmetric, kurtosis 2.37 |
| `uniform` | $1+c\sqrt3\,(2u-1)$ | $1\pm1.732\,c$ | symmetric, kurtosis 1.8 |
| `lognormal` | $e^{\sigma z(u)}/m$, with $\sigma$ and $m$ solved so that the mean is 1 and the coefficient of variation is $c$ | $e^{\mp2\sigma}/m$, e.g. 0.49 to 1.89 at $c=0.3$ | skewed to the right: median below mean |

- A configuration is rejected when a shape could give a value of zero or less
  (`normal` from $c=0.44$, `uniform` from $c=0.58$).
- Because a driver keeps their percentiles, the same driver is at the same rank of the
  population under every shape and every $c_\theta$: cases can be compared seed by seed.
- For $v_0$ the factor multiplies the desired speed of every road section the driver
  uses; for $b_{\rm safe}$ it multiplies the limit the driver applies to their own
  mandatory lane changes. $\delta$ and the vehicle length are not varied.
- The equilibrium relations above hold driver by driver. A mixed platoon has no single
  equilibrium gap, and on one lane without passing it moves no faster than its slowest
  driver wants to.

Which parameters real drivers differ in, by how much and with which shape is recorded,
with sources, in the [driver heterogeneity review](../research/driver_heterogeneity.md).
Independence between parameters is a simplification that review discusses. Every
$c_\theta$ used in this repository is taken from other sites or other models, not
estimated here: fitting five-minute aggregates alone cannot uniquely identify all
behavioral parameters.
