# The queue estimate and a short-horizon forecast, scored against truth

A small check for the course's observation component (guide p. 3), run on 2026-11-19
after the calibration. Simulated: the calibrated baseline day, ALINEA, seed 1.
`uv run python scripts/forecast_check.py`. Forecasting as a research component is out of
scope (D020); this scores what the meter already does.

## Question

The meter's queue rule uses two things it cannot see directly: the number of vehicles
queued on the ramp, estimated from the counts of the entry loop and the passage loop,
and the next interval's ramp arrivals, taken to equal the last interval's. How good are
the two, and what happens when the entry loop stops reporting?

## Method

- **State estimate.** Queue = vehicles counted in at the entry loop (18 m from the
  ramp entrance) less vehicles counted out at the passage loop (just past the stop
  line). Truth: vehicles upstream of the stop line plus those waiting on the street.
- **Forecast, horizon 30 s.** The count of the next 30-second interval at the entry
  loop. Method in use: the last value. Simple baseline, as the guide suggests: the mean
  of the last ten intervals. Neither has a fitted parameter, so there is no development
  period to separate; scores are from 06:00 on, after the first hour has filled the
  window.
- **Observation defect.** The entry loop reports nothing from 06:30 to 07:30. Each
  method then uses the last values it has.
- Error measure: mean absolute error, in vehicles and in vehicles per interval. Truth
  is used only to score.

## Result

| Quantity | Value |
| --- | --- |
| Ramp arrivals per 30 s at the entry loop, mean | 6.6 veh |
| Forecast error, last value (in use) | 1.20 veh per interval |
| Forecast error, ten-interval mean (baseline) | 1.30 veh per interval |
| The same during the hour without the loop: last value / mean | 2.02 / 2.03 veh per interval |
| True queue, mean and largest | 83 and 156 veh |
| Queue estimate error, all samples | 62.8 veh (bias −62.6) |
| Queue estimate error while the queue fits upstream of the stop line (11 % of samples) | 1.8 veh |

## Interpretation

- The last value does slightly better than the moving average, by about 8 %. Once the
  queue covers the entry loop the count is the meter's own release rate, which changes
  little from one interval to the next. With the loop missing both forecasts go stale
  and their errors rise to about 2 vehicles per interval.
- **The queue estimate is good only while the queue is on the ramp.** The entry loop
  sits 18 m inside the ramp; vehicles that have not reached it are not counted. On this
  day the queue exceeds the storage upstream of the stop line 89 % of the time after
  06:00, and the estimate is then short by everything beyond the entry loop. The queue rule therefore sees a full ramp, not how
  long the queue beyond it is. This matters for reading the study's results: the peak
  queue on Ventura Blvd is simulator truth, not something the modeled controller knows.

## Limits

One seed and one day. The forecast is of the loop's count, which is not the demand
arriving from the street once the queue covers the loop. No estimator or forecast method
was developed; the check scores the two that are in the code.
