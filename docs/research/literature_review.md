# Literature foundation and source-to-design record

This is a targeted starting bibliography, not a systematic review. Links and source
identities were checked on 2026-11-07. Public metadata/full text was consulted as
noted below; no reported result is transferred to the I-405 site. Sources added
later are listed in the record that uses them: the Caltrans metering documents in
[i405_ablation.md](../i405_ablation.md#sources), the calibration guidance in
[calibration.md](../../experiments/calibration.md#sources), the merge and bottleneck
papers in [ramp_mainline_mix.md](../../experiments/ramp_mainline_mix.md#sources), and
the driver-variation literature in [driver_heterogeneity.md](driver_heterogeneity.md).
Parameter values and their origin are in `configs/i405.yaml`. Equations in this
repository are background or explicitly labeled project proposals.

## Verified starting references

1. **Treiber, M., and Kesting, A. (2013).** *Traffic Flow Dynamics: Data, Models and
   Simulation*. Springer. [DOI: 10.1007/978-3-642-32460-4](https://doi.org/10.1007/978-3-642-32460-4).
   Bibliographic information verified on the [authors' book site](https://traffic-flow-dynamics.org/);
   full book not reviewed here. The site also lists a 2025 second edition. Use an
   explicit edition when recording chapter/page references; confirm which edition
   the course's suggested chapter numbers refer to.
2. **Treiber, M., Hennecke, A., and Helbing, D. (2000).** “Congested traffic states
   in empirical observations and microscopic simulations.” *Physical Review E*,
   62(2), 1805–1824. [DOI: 10.1103/PhysRevE.62.1805](https://doi.org/10.1103/PhysRevE.62.1805).
   [Publisher full text](https://harvest.aps.org/v2/journals/articles/10.1103/PhysRevE.62.1805/fulltext),
   especially Section II: original IDM and behavioral assumptions. Its empirical
   examples are not Los Angeles calibration data.
3. **Treiber, M., traffic-simulation.de (undated).** *The Intelligent-Driver Model
   and its Variants*. [Author's technical notes](https://traffic-simulation.de/info/info_IDM.html).
   Supplement for the standard gap form, closing-speed convention, ballistic
   integration, and stopped-vehicle handling; not a replacement for the original paper.
4. **Papageorgiou, M., Hadj-Salem, H., and Blosseville, J.-M. (1991).** “ALINEA:
   A Local Feedback Control Law for On-Ramp Metering.” *Transportation Research
   Record*, 1320, 59–64. [Original TRB paper](https://onlinepubs.trb.org/Onlinepubs/trr/1991/1320/1320-008.pdf).
   Equation 14 supplies the feedback law; the restrictions/override discussion
   distinguishes normal command memory from constrained operation. No DOI asserted.
5. **Daganzo, C. (1994).** *The Cell Transmission Model: Network Traffic*.
   Working paper UCB-ITS-PWP-94-12, University of California, Berkeley.
   [Institutional record and report](https://escholarship.org/uc/item/9pz309w7).
   Basis of the synthetic CTM demo (removed 2026-11-19), whose equations and
   merge assumptions are recorded separately. This is not a chosen second model
   or evidence that a macroscopic model validates individual trajectories.
6. **California Department of Transportation (2022).** *Ramp Metering Design
   Manual*, October 2022. [Official PDF](https://dot.ca.gov/-/media/dot-media/programs/traffic-operations/documents/ramp-metering/202210-rmdm-a11y.pdf).
   Reference for geometry, storage, and equipment questions. Do not use generic
   design values as measurements of this ramp.
7. **California Department of Transportation (2025).** *Traffic Operations Manual*,
   Chapter 215, Part 4, *Ramp Metering Operations*, April 2025.
   [Official PDF](https://dot.ca.gov/-/media/dot-media/programs/traffic-operations/documents/trafficops/202504-ch-215-pt-4-ramp-metering-operations-a11y.pdf).
   Operational context for local traffic-responsive plans, queue handling, and PeMS
   interpretation. Chapter/version confirmed against the [manual index](https://dot.ca.gov/programs/traffic-operations/traffic-ops-manual).
8. **Koonce, P., et al. (2008).** *Traffic Signal Timing Manual*. FHWA-HOP-08-024,
   Federal Highway Administration, June 2008.
   [Report metadata](https://ops.fhwa.dot.gov/publications/fhwahop08024/doc_page.htm)
   and [introductory chapter](https://ops.fhwa.dot.gov/publications/fhwahop08024/chapter1.htm).
   Historical signal terminology/reference only: FHWA marks this edition archived
   and superseded. Review the replacement and relevant course material before
   selecting the final signal controller or timing assumptions.

The locally reviewed course guide is documented with its checksum and page map in
[scope and assumptions](scope_and_assumptions.md); no public source URL is invented.

## Source-to-design table

| Design element | Basis | Interpretation and remaining work |
| --- | --- | --- |
| Flow/density/speed and conservation | Treiber–Kesting; Daganzo | Common definitions plus explicit project units; choose aggregation and diagram before calibration |
| IDM law and assumptions | Original IDM; author's notes | Candidate standard variant; record any changes and validate discretization |
| ALINEA update | Original ALINEA, Eq. 14 | Established law; gain (assumed), target (critical occupancy, D022), 30 s interval and one-vehicle-per-green release are set in `configs/i405.yaml`, not calibrated |
| Slew limit, timeout fallback, quality gates | Project proposals informed by operational requirements | Must be justified and evaluated separately from baseline ALINEA |
| Differences between drivers (spread, shape, lane-changing preference) | [Driver heterogeneity review](driver_heterogeneity.md) of 2026-11-18: simulator documentation, the IDM authors' papers, field and calibration studies | Optional in the engine (D018, D019); every spread comes from another site or another model, and parameters are drawn independently |
| IDM parameter values at the site | FHWA Traffic Analysis Toolbox Vol. III (2004, 2019); Dervisoglu et al. (2009); Treiber and Kesting (2013); Lecture 05B, slide 28 | `v0`, `T` and `delta` calibrated on PeMS and checked on held-out days (`scripts/calibrate_fd.py`, [record](../../experiments/calibration.md), D023); `s0`, `a`, `b` keep sourced values because loop data cannot identify them |
| ALINEA set value | Papageorgiou et al. (1991), read in full; Lecture 05B, slide 26 | The critical occupancy of the configured model as the loop sees it; a test recomputes it for every configuration (D022). The queue rule's source (Smaragdis and Papageorgiou 2003) could not be opened |
| Caltrans local traffic-responsive plan and queue override | Caltrans Traffic Operations Manual ch. 215; District 7 manuals and reports ([sources](../i405_ablation.md#sources)) | The structure follows the documents; the plan values for this ramp are unpublished and assumed (D015) |
| Whether the merge is an active bottleneck | Chen, Skabardonis and Varaiya (2004); Lecture 05B, slides 3 to 5; Lecture 03 (shockwave speed) | `scripts/bottleneck_check.py`: observed lanes only, eight weekdays ([record](../../experiments/ramp_mainline_mix.md#site-characterization-pems-observed), D021) |
| What can be said before a run: static capacity, deterministic queue, capping strategy | Lecture 03 (capacity, D/D/1 queue); Lecture 05B, slides 22 and 23 (capping strategy) | `ablation.analytic_table`, printed by `arm-ablation --analytic` (D021) |
| How queued ramp and freeway traffic share a merge | Cassidy and Ahn (2005); Bar-Gera and Ahn (2010), abstracts only | Used for a written prediction, not implemented as a model (D021) |
| Decision rule for comparisons | Paired differences over seeds with 95 % t intervals; FHWA (2004, Appendix B) on repetitions | `drivers.interval`; a difference counts above a stated size (D016, D019, D021) |
| Signal pathway | Course guide p. 6; FHWA background | Obtain scaffold and at least two substantive final-pathway sources, including a controller method or authoritative description |

## Reading still needed

Select sources for the merge rule itself, observation/state estimation, and the final
pathway's controller. The course expects at least two relevant observation/prediction
sources and at least two final-pathway sources; forecasting is out of scope since
2026-11-18 (D020). This initial list does not claim that all future literature
requirements are satisfied.

For each later source, record the claim used, exact equation/section, assumptions,
parameter evidence, and the implementation or validation check it informs. Record
disagreements and limitations rather than copying convenient parameter values.
