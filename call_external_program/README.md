# call_external_program

Minimal EnergyPlus Python API example for answering [Unmethours #103282: "E+ pause the simulation, get data, change schedules, continue simulation"](https://unmethours.com/question/103282/e-pause-the-simulation-get-data-change-schedules-continue-simulation/).

The question asks how to pause an EnergyPlus simulation mid-run, hand off to an
external program to compute something (e.g. next-day setpoints from an
external model), and feed the result back into the simulation via a
schedule actuator — without stopping and restarting E+.

## How it works

- `test.idf` — a bare-bones one-zone-less model (no zones/surfaces needed)
  with a single `Schedule:Constant` named `TestSchedule`, reported every
  timestep via `Output:Variable` / `Output:SQLite`.
- `test_external_program_everyday.py` — drives the simulation through the
  EnergyPlus Python API (`pyenergyplus.api.EnergyPlusAPI`):
  - Registers a `callback_begin_system_timestep_before_predictor` callback
    (`HeatingSetpointProg.on_begin_timestep_before_predictor`).
  - Once per simulated day (at hour 0, first zone timestep), it calls
    `calculate_next_day_hourly_values()` — a stand-in for "call an external
    program/model" — to compute the next 24 hourly values.
  - Every timestep, it pushes the current hour's value into the simulation
    by setting the `TestSchedule` actuator via
    `api.exchange.set_actuator_value`.
  - After the run, `parse_sql()` reads the resulting `eplusout.sql` and
    plots the actuated schedule values to confirm they made it into the
    simulation as expected.
- `out/` — EnergyPlus output directory from running the script (SQL, ESO,
  logs, etc.).

## Running

```bash
python test_external_program_everyday.py
```

Requires EnergyPlus 25.2 installed at `/Applications/EnergyPlus-25-2-0/`
(adjust the `sys.path.insert` call at the top of the script otherwise).

This is scratch/debugging code for a forum answer, not production code.
