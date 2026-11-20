# Driver heterogeneity: what simulators and studies use

Review of 2026-11-18 for decision D019: which driver parameters to vary in the
microscopic model, by how much and with which distribution shape. It is a targeted
review, not a systematic one, and no value here is a measurement of the I-405 site.

How each entry was checked:

- **[run]** checked by running the software in this project's environment.
- **[read]** the quote or number was re-opened in the source on 2026-11-18 (web page, or
  the paper's PDF text) after the first research pass reported it.
- **[reported]** found by the research pass with a quote and a link, not re-opened.
  Re-open before citing it in the paper.

Coefficients of variation (CV = standard deviation / mean) marked "computed" are this
project's arithmetic from a source's mean and standard deviation.

## Answers in short

1. **Which parameters do simulators vary between drivers?** Desired speed, in every tool
   read. Time gap, acceleration, deceleration and standstill gap only in some, and often
   with zero spread by default. Lane-changing parameters are fixed sets; differences
   enter through driver types or a share of cooperating drivers.
2. **Which shape?** A truncated normal is the standard for continuous traits (SUMO,
   Aimsun, Vissim's internal random values). The alternatives in use are tables of
   driver types or empirical curves (CORSIM, Vissim desired speed, TransModeler,
   Paramics) and a uniform (the IDM authors' own tools and papers). Lognormal and gamma
   exist only as options (SUMO's type-distribution tool), never as a default.
3. **What do field and calibration studies find?** Desired speed is close to normal with
   a CV of 0.10 to 0.15. Time gap, standstill gap, acceleration and comfortable
   deceleration are skewed to the right, with spreads two to eight times wider than
   simulator defaults; lognormal is the family most often fitted or assumed.
4. **Lane changing.** Gap-acceptance models draw critical gaps from a lognormal with one
   persistent term per driver. Nobody randomizes MOBIL's safety limit `b_safe`; its
   authors report that results barely depend on it.
5. **Is one shape preferred?** No guideline read prescribes a family, and no study read
   compares uniform, normal and lognormal at equal mean and spread. The evidence that
   does exist is mixed (section 5). That comparison is what
   [the experiment](../../experiments/driver_populations.md) does for this model.

## 1. Simulators

| Tool | What differs between drivers by default | Family and values | Check |
| --- | --- | --- | --- |
| Eclipse SUMO 1.28 | Only the desired-speed factor. `accel` 2.6, `decel` 4.5, `tau` 1.0, `minGap` 2.5 and all lane-change parameters are one value per vehicle type | Normal factor on the speed limit, mean 1, sd 0.1, cut at 0.2 and 2 (`normc(1,0.1,0.2,2)`). 20,000 default cars: mean 0.999, sd 0.100, range 0.62 to 1.38, skewness 0.01, kurtosis 2.97 | [run]; docs sentence [reported] |
| SUMO, `createVehTypeDistribution.py` | Any attribute, if the user builds a type population | `normal`, `normalCapped`, `lognormal`, `uniform`, `gamma`, each attribute on its own; values outside the limits are redrawn, then cut | [read] (installed source) |
| Aimsun Next 26 | "Almost all parameters are defined using a truncated normal distribution" (mean, deviation, minimum, maximum). Lane changing: ranges "to randomize behavior for each vehicle", and a percentage of vehicles that cooperate | Documented example: desired speed 110 km/h, deviation 10, between 90 and 140 | [read] |
| Aimsun, default car values | Acceleration 3 ± 0.2 (2.6 to 3.4) m/s², normal deceleration 4 ± 0.25, maximum deceleration 6 ± 0.5, minimum distance 1 ± 0.3 (0.5 to 1.5) m | Truncated normal; computed CV 0.07, 0.06, 0.08, 0.30 | [reported], second-hand from a 2012 thesis |
| PTV Vissim 2025 | Desired speed (an empirical curve); acceleration between a minimum and a maximum curve; Wiedemann 74 standstill distance and safety distance | The random value is "normally distributed with an average value of 0.5 and a standard deviation of 0.15, but is limited to [0..1]". Standstill distance 2.0 m plus a normal tolerance, sd 0.3 m, within ±1.0 m (computed CV 0.15) | [read] |
| Vissim, Wiedemann 99 and lane change | CC1 (time gap) is a distribution with no spread by default, 0.9 s; other parameters and all lane-change thresholds are fixed per behavior set | – | [reported] |
| CORSIM / FRESIM | Ten driver types "that increase in aggressiveness from 1 to 10" | Car-following sensitivity "1.25 to 0.35 s based on driver type, mean = 0.80 s"; free-flow speed "88–112% based on driver type". Ten evenly spaced values are close to a uniform: computed CV 0.36 and 0.08 | [read]; individual values [reported] |
| Paramics | Aggression and awareness levels 0 to 8, which modulate a 1.0 s mean headway | Bell-shaped default histogram 1, 4, 11, 21, 26, 21, 11, 4, 1 % | [reported] |
| TransModeler | Tables of "percent of drivers" for desired speed, headway, acceleration | Discrete; stopped gap 11.3 ft with sd 3.9 ft | [reported], from a state guideline |
| MovSim and traffic-simulation.de (Treiber, Kesting) | Desired speed, off by default in MovSim; one factor on `v0` and `a` in the web simulator | Uniform; CV 0.15 in the web simulator (`driver_varcoeff=0.15`, factor `1+sqrt(12)·0.15·(U−0.5)` on `v0` and `a`; `T`, `s0`, `b` unscaled although a code comment names `T`) | web simulator [read] 2026-11-19; MovSim [reported] |

## 2. The IDM authors' own practice

- Kesting, Treiber and Helbing (2010) vary `v0`, `T`, `a` and `b` "uniformly and
  independently", each between 80 % and 120 % of the mean (computed CV 0.115), on a
  freeway with an on-ramp; more heterogeneity widens the spread of the maximum free flow
  and slightly lowers its mean. Car values in their Table 1: 120 km/h, 1.5 s, 2.0 m,
  1.4 and 2.0 m/s². Table and sentences [read] (PDF text, 2026-11-19): "assigning uniformly and
  independently distributed values to the IDM parameters v0, T, a and b, where the
  averages of the parameter values have been left unchanged".
- Kesting, Treiber and Helbing (2008): "it is straightforward to distribute individual
  agent parameters randomly within given limits, e.g. according to a uniform
  distribution with a variation of 20%", next to driver classes (normal, timid,
  aggressive, truck) in which an aggressive driver has a high `v0`, `a`, `b` and a low
  `T` and `s0`. [read]
- Kesting et al. (2007), a single-lane road with an on-ramp, the closest published case
  to this model: "We have compared the simulation results with Gaussian distributed model
  parameters, but found no qualitative difference for this single-lane scenario", and
  distributed parameters lower the outflow from congested traffic "while such an effect
  is not observed for the free-flow capacity". [read]

## 3. Field and calibration evidence per parameter

| Parameter | Evidence | Shape | CV | Check |
| --- | --- | --- | --- | --- |
| Desired speed | FHWA speed guide: "Operating speeds have been found to be normally distributed". 42 Shanghai expressway drivers, observed: 82.1 ± 12.1 km/h | normal | 0.10 (SUMO) to 0.15 (observed, computed) | Shanghai [read]; FHWA not confirmed (page refused on 2026-11-19) |
| Time gap `T` | 98 drivers, Michigan: each driver's mean time gap on highways is fitted with a lognormal, mean 1.42 s, variance 0.08 s², quartiles 1.21 / 1.39 / 1.60 s. Shanghai, observed: 1.80 ± 0.35 s. Shanghai, calibrated IDM `T`: 0.88 ± 0.33 s | lognormal across drivers | 0.20 observed (computed); 0.38 calibrated | [read] |
| Maximum acceleration `a` | Shanghai, calibrated: mean 0.84, median 0.81, sd 0.28 m/s². NGSIM fits are right-skewed, lognormal chosen over normal, gamma and logistic | right-skewed | 0.33 calibrated (computed) | Shanghai [read]; NGSIM: data set and per-style maximum-likelihood calibration [read], the choice of lognormal [reported] |
| Comfortable deceleration `b` | Shanghai, calibrated: mean 0.82, median 0.61, sd 0.73 m/s², 5th percentile 0.12 on a lower search bound of 0.1 | strongly right-skewed, poorly identified | 0.89 calibrated (computed) | [read] |
| Standstill gap `s0` | 1,140 car-behind-car standstill distances on Iowa freeways: mean 9.41 ft, median 8.80 ft, sd 4.54 ft; "right-skewed (long tail to the larger values)". Shanghai, calibrated: 1.56 ± 0.96 m | right-skewed | 0.48 observed (computed); 0.62 calibrated | [read] |

Two cautions carried into the choice of cases. First, the calibrated spreads pool 42
drivers with five cross-validation folds and sit partly on search bounds, and several
studies find that variation within a driver is as large as variation between drivers
([read], abstracts: Kesting and Treiber 2008, "intra-driver variability" rather than
"inter-driver variability" accounts for a large part of the calibration errors; Kurtc
2020 on highD, "Intradriver variation accounted for a larger portion of the calibration
errors than interdriver variation"), so they are upper estimates of
between-driver spread. Second, studies that plot calibrated IDM parameters for NGSIM
describe them as multimodal or fat-tailed and warn against sampling them from a Gaussian
([reported]: Kujanpää et al. 2024; not in their abstract, body not re-read).

## 4. Lane changing and gap acceptance

- **Critical gaps are lognormal with one driver term.** Toledo, Koutsopoulos and
  Ben-Akiva (2003): "Critical gaps are assumed to follow lognormal distributions to
  ensure that they are always nonnegative", with an individual-specific term per driver
  and a random term per decision, estimated on 442 vehicles and 15,632 observations from
  I-395. [read] In their estimates the driver term is large for the lead gap and small
  for the lag gap [reported]. Accepted gaps at the NGSIM I-80 merge are also fitted well
  by a gamma (Bham 2008: "Accepted, LRLA, and critical gaps were assumed to follow a gamma
  distribution", after fitting gamma and lognormal with a Kolmogorov-Smirnov test) [read].
- **MOBIL's safety limit is not randomized, and matters little.** Kesting, Treiber and
  Helbing (2007) use `b_safe` = 4 m/s² for every vehicle; it "should be well below the
  maximum possible deceleration bmax, which is about 9 m/s2", and its influence "is
  negligible within a reasonable range of braking accelerations from −8 m/s2 to −b".
  They vary only the desired speed, "uniformly ... with a variation of ±20%", and name
  "statistically distributed values for the MOBIL parameters, particularly for the
  politeness parameter" as a way to represent driver diversity. The on-ramp merge is "a
  'virtual vehicle' standing at the end of the merging lane". [read]
- **Simulators** keep lane-change thresholds fixed per behavior set; Vissim's preset
  driving styles range from 0.5 to 5 m/s² of accepted deceleration, and Aimsun and CORSIM
  set a share of drivers who cooperate. [reported]
- **What this means here.** The model's only lane-change threshold is `b_safe`, so the
  lane-changing preference is a per-driver factor on it for the merging driver's own
  decisions. No source gives a fitted spread for `b_safe`; 0.25 is assumed and a
  lognormal is used because that is the family of the gap-acceptance literature. A
  driver's own IDM values already make their critical gap differ, since the safety test
  uses their own acceleration function.

## 5. Shape, spread and correlation: what is known

- **Shape.** No study read compares uniform, normal and lognormal at equal mean and
  spread. Normal and lognormal car-following sensitivities did equally well in CORSIM
  once mean and variance were calibrated (Schultz and Rilett 2004), and for congested
  patterns in Newell's model only the means matter (Chiabaut, Leclercq and Buisson 2010)
  [reported; not confirmed on 2026-11-19: the first was not found in OpenAlex, the second
  has no abstract there]. Against that, Punzo and Montanino (2020), on three NGSIM I-80
  scenarios: "normal distributions of the model parameters ... have been found unable to
  reproduce the observed congestion patterns". [read, abstract]
- **Spread.** More heterogeneity lowers outflow from congestion and widens the range of
  flows at which traffic breaks down (section 2).
- **Correlation.** Kim and Mahmassani (2011) report that simulated outputs differ
  significantly when correlation between a driver's parameters is kept instead of
  ignored, and that a multivariate-normal fit may not remove the error when normality
  fails [read, abstract, Crossref 2026-11-19]; Punzo and Montanino (2020) add that correlation "is
  responsible for a model overfitting in traffic scenarios with low congestion" [read,
  abstract]. FHWA's 2020 calibration report recommends joint distributions that keep the
  correlation [reported]. No numeric across-driver correlation matrix for IDM parameters
  was found, so this project draws parameters independently and says so.
- **Guidelines.** FHWA's Traffic Analysis Toolbox and the state and city guidelines read
  ask for field-measured speed distributions and for adjusting mean headway-type
  parameters; none prescribes a family [reported].

## 6. Cases chosen for this project

Defined in `configs/i405_drivers.yaml`; spreads are CVs around the site's fixed values.

| Case | Spread and shape | Why |
| --- | --- | --- |
| `fixed` | none | the model behind every earlier result |
| `speed_only` | `v0` 0.10, normal | what a mainstream simulator does by default (SUMO) |
| `uniform` | `v0`, `T`, `a`, `b` 0.1155, uniform | the IDM authors' rule: independent, 80–120 % of the mean |
| `normal`, `lognormal` | the same four at 0.1155 | the same mean and spread in the simulators' usual shape and in a skewed one |
| `merge_only` | `b_safe` 0.25, lognormal | the lane-changing preference on its own |
| `empirical` | `v0` 0.10 normal; lognormal `T` 0.20, `a` 0.33, `b` 0.33, `s0` 0.48, `b_safe` 0.25 | spreads observed or calibrated at other sites, each skewed parameter lognormal |

Choices that are this project's own: `b` gets the spread of `a` because its calibrated
0.89 sits on search bounds; `v0` stays at 0.10 in `empirical` although 0.15 was observed,
because the model has one freeway lane without passing and a wider spread would put the
slowest drivers under the 20 m/s congestion line by construction; the normal is
truncated at two standard deviations, where SUMO's default is practically untruncated.

## 6a. Checked against the course lectures (2026-11-19)

The CEE 181/281 lectures in `docs/lectures/` were searched for driver heterogeneity,
distributions, IDM parameters and gap acceptance.

| Lecture and slide | What it says | Bearing on this review |
| --- | --- | --- |
| 05B, slide 28 | The preferred time gap `T` is "the most relevant influencing factor determining the static capacity"; an agile driving style reduces the capacity drop and brings the dynamic capacity nearer to the static one | A mean-preserving spread of `T` leaves the static capacity of a platoon unchanged (computed), yet costs 1.45 min per vehicle on the calibrated model, and a spread of `a` costs 3.22 ([driver traits](../../experiments/driver_traits.md)): the dynamic side dominates, as the slide's agility point implies |
| 05B, slides 15–16 | Speed limits "homogenize traffic flow with respect to the speed distribution"; the desired speed should be a parameter of a microscopic model | Treats drivers' speeds as a distribution; no shape given |
| 03, slides 65–67 | Raff's critical gap: the gap at which the number of accepted gaps shorter than it equals the number of rejected gaps longer than it (worked example 3.14 s) | One population value summarizing drivers who differ; the lecture assigns no distribution to it |
| 03, slides 68–70 | Gap acceptance with Poisson main-stream arrivals and one critical gap (on-ramp example: 3.5 s at 1,800 veh/h) | Arrivals in the model are Poisson, as in the lecture; the model's merge uses MOBIL's safety test, not a critical gap |
| 02, slides 12–16 | Spot speed studies estimate the distribution of speeds; free vehicles have at least 4 s of headway (FHWA) | Mean, standard deviation and percentiles of speeds; no distribution family named in the text |

Nothing in the lectures prescribes a distribution family for driver parameters, and
nothing contradicts the review.

## 7. Not verified or not found

- An across-driver correlation matrix for IDM parameters; mean and sd of per-driver IDM
  fits on NGSIM or highD.
- Full texts behind paywalls: Kim and Mahmassani (2011), Punzo and Montanino (2020),
  Ossen and Hoogendoorn (2011), Kurtc (2020), Hoogendoorn (2005), Ahmed (1999), and the
  lane-changing chapter of Treiber and Kesting's book.
- Current numeric defaults of Aimsun and of Vissim's speed and acceleration curves.
- A fitted distribution of `b_safe` or of the deceleration that merging imposes on the
  following vehicle.

## Sources

1. Eclipse SUMO documentation, "Definition of Vehicles, Vehicle Types, and Routes":
   <https://sumo.dlr.de/docs/Definition_of_Vehicles%2C_Vehicle_Types%2C_and_Routes.html>;
   tool `createVehTypeDistribution.py`: <https://sumo.dlr.de/docs/Tools/Misc.html>.
2. Aimsun Next 26 Users Manual, vehicle types:
   <https://docs.aimsun.com/next/26.0.0/UsersManual/VehicleTypeEditing.html>.
3. PTV Vissim 2025 help, stochastic distribution of values and Wiedemann 74:
   <https://cgi.ptvgroup.com/vision-help/VISSIM_2025_ENG/Content/4_BasisdatenSim/StochastischeWerteverteilung.htm>,
   <https://cgi.ptvgroup.com/vision-help/VISSIM_2025_ENG/Content/4_BasisdatenSim/FahrverhaltensparameterFolgeverh_Wied74.htm>.
4. FHWA-HRT-04-131, chapter 5 (CORSIM parameters):
   <https://www.fhwa.dot.gov/publications/research/operations/its/04131/05.cfm>; FHWA
   Traffic Analysis Toolbox Vol. IV, appendix A:
   <https://ops.fhwa.dot.gov/trafficanalysistools/tat_vol4/app_a.htm>.
5. Kesting, A., Treiber, M., and Helbing, D. (2010). "Enhanced intelligent driver model
   to access the impact of driving strategies on traffic capacity." *Phil. Trans. R. Soc.
   A* 368, 4585–4605. <https://arxiv.org/abs/0912.3613>.
6. Kesting, A., Treiber, M., and Helbing, D. (2008). "Agents for Traffic Simulation."
   <https://arxiv.org/abs/0805.0300>.
7. Kesting, A., Treiber, M., Schönhof, M., Kranke, F., and Helbing, D. (2007).
   "Jam-avoiding adaptive cruise control (ACC) and its impact on traffic dynamics."
   *Traffic and Granular Flow '05*, 633–643, Springer.
   <https://arxiv.org/abs/physics/0601096>.
8. Kesting, A., Treiber, M., and Helbing, D. (2007). "General lane-changing model MOBIL
   for car-following models." *Transportation Research Record* 1999, 86–94.
   <https://www.mtreiber.de/publications/MOBIL_TRB.pdf>.
9. Zhu, M., Wang, X., Tarko, A., and Fang, S. (2018). "Modeling car-following behavior
   on urban expressways in Shanghai: A naturalistic driving study." *Transportation
   Research Part C* 93, 425–445. <https://arxiv.org/abs/1811.06395>.
10. Huang, X., Zhang, S., and Peng, H. (2018). "Developing Robot Driver Etiquette Based
    on Naturalistic Human Driving Behavior." <https://arxiv.org/abs/1808.00869>.
11. Dong, J., Houchin, A., Shafieirad, N., Lu, C., Hawkins, N., and Knickerbocker, S.
    (2015). *VISSIM Calibration for Urban Freeways*. Institute for Transportation, Iowa
    State University. <https://rosap.ntl.bts.gov/view/dot/38676/dot_38676_DS1.pdf>.
12. Toledo, T., Koutsopoulos, H., and Ben-Akiva, M. (2003). "Modeling integrated
    lane-changing behavior." *Transportation Research Record* 1857, 30–38.
    <https://toledo.net.technion.ac.il/files/2012/12/TRR_LC_03.pdf>.
13. Punzo, V., and Montanino, M. (2020). "A two-level probabilistic approach for
    validation of stochastic traffic simulations: impact of drivers' heterogeneity
    models." *Transportation Research Part C* 121, 102843.
    <https://doi.org/10.1016/j.trc.2020.102843>.
14. Re-opened 2026-11-19 (abstract or PDF text): Kim and Mahmassani (2011), *TRR* 2249,
    62–77, <https://doi.org/10.3141/2249-09>; Bham (2008),
    <https://rosap.ntl.bts.gov/view/dot/40452/dot_40452_DS1.pdf>; Kesting and Treiber
    (2008), *TRR* 2088, 148–156, <https://arxiv.org/abs/0803.4063>; Kurtc (2020), *TRR*
    2674(8), 813–822, <https://doi.org/10.1177/0361198120925063>. Reported only, to
    re-open before citing: Schultz and Rilett (2004), *TRR* 1876; Chiabaut, Leclercq and
    Buisson (2010), *Transportation Research Part B* 44(2), 299–308; Kujanpää et al.
    (2024), <https://arxiv.org/abs/2401.03236>; Sun et al. (2024), *Intelligent
    Transportation Infrastructure* 3, liae010; FHWA *Speed Concepts: Informational
    Guide*; FHWA-HOP-20-057, <https://ops.fhwa.dot.gov/publications/fhwahop20057/ch5.htm>;
    Ronaldo and Ismail (2012), Linköping thesis with Aimsun defaults,
    <https://www.diva-portal.org/smash/get/diva2:555913/FULLTEXT01.pdf>.
