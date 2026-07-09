import datetime
from pathlib import Path
import sqlite3
import sys

# insert the repo build tree or install path into the search Path, then import the EnergyPlus API
sys.path.insert(0, "/Applications/EnergyPlus-25-2-0/")

# sys.path.insert(0, r'C:\EnergyPlusV25-2-0\')
from pyenergyplus.api import EnergyPlusAPI

import pandas as pd
import matplotlib.pyplot as plt


def calculate_next_day_hourly_values():
    """This can be a subprocess.check_call to an external program"""
    return [0.1 * i for i in range(24)]


class HeatingSetpointProg:

    def __init__(self, api):
        self.api = api

        self.need_to_get_handles = True
        self.handles = {
            "actuator_schedule": -1,
        }
        self.num_time_steps_in_hour = -1
        self.next_day_values: list[float] = [0.0] * 24
        self.values = []

    def get_datetime(self, state):
        hr = self.api.exchange.hour(state)
        mn = self.api.exchange.minutes(state)
        d = self.api.exchange.day_of_month(state)
        m = self.api.exchange.month(state)
        y = self.api.exchange.calendar_year(state)
        # current_time = self.api.exchange.current_time(state)  # fractional hours

        # Construct Python datetime
        # Note: hours from API already 0–23, minutes 1–60
        dt = datetime.datetime(y, m, d, hr, mn - 1) + datetime.timedelta(minutes=1)
        return dt

    def on_begin_timestep_before_predictor(self, state) -> int:
        if not self.api.exchange.api_data_fully_ready(state):
            return 0

        if self.api.exchange.warmup_flag(state):
            return 0

        if self.need_to_get_handles:

            self.handles["actuator_schedule"] = self.api.exchange.get_actuator_handle(
                state, "Schedule:Constant", "Schedule Value", "TestSchedule"
            )

            for k, h in self.handles.items():
                if h == -1:
                    print(f"Could not get handle to {k}")
                    self.api.runtime.issue_severe(state, f"Could not get handle to {k}")
                    self.api.runtime.stop_simulation(state)
                    return 1

            self.api.exchange.num_time_steps_in_hour
            self.need_to_get_handles = False

        if self.api.exchange.hour(state) == 0 and self.api.exchange.zone_time_step_number(state) == 1:
            # dt = self.get_datetime(state)
            # print(f"{dt}: hour={self.api.exchange.hour(state)}, minutes={self.api.exchange.minutes(state)},"
            #       f"zone_time_step={self.api.exchange.zone_time_step(state)},"
            #       f"zone_time_step_number={self.api.exchange.zone_time_step_number(state)},"
            #       f"system_time_step={self.api.exchange.system_time_step(state)}")
            self.next_day_values = calculate_next_day_hourly_values()

        sch_val = self.next_day_values[self.api.exchange.hour(state)]
        self.api.exchange.set_actuator_value(state, self.handles["actuator_schedule"], sch_val)
        return 0


def parse_sql(sql_path: Path) -> pd.Series:

    sql_uri = f"{sql_path.absolute().as_uri()}?mode=ro"
    print(f"{sql_uri=}")

    query = """
SELECT Month, Day, Hour, Minute,
       ReportingFrequency, KeyValue, Name, Units, Value
FROM ReportVariableWithTime
WHERE EnvironmentPeriodIndex == 1
    AND Name='Schedule Value'
    AND KeyValue='TESTSCHEDULE'
"""
    with sqlite3.connect(sql_uri, uri=True) as con:
        df = pd.read_sql(query, con=con)

    filt = df["Hour"] == 24
    df.loc[filt, "Hour"] = 23
    df.loc[filt, "Minute"] = 59

    year = 2013
    df["Timestamp"] = pd.to_datetime(
        (year * 100000000 + df.Month * 1000000 + df.Day * 10000 + df.Hour * 100 + df.Minute).apply(str),
        format="%Y%m%d%H%M",
    )
    df.loc[filt, "Timestamp"] += datetime.timedelta(minutes=1)

    df_pivot = pd.pivot_table(
        df,
        values="Value",
        columns=["ReportingFrequency", "KeyValue", "Name", "Units"],
        index=["Timestamp"],
    )

    return df_pivot


if __name__ == "__main__":
    api = EnergyPlusAPI()
    state = api.state_manager.new_state()
    debug_prog = HeatingSetpointProg(api=api)
    api.runtime.callback_begin_system_timestep_before_predictor(state, debug_prog.on_begin_timestep_before_predictor)
    api.runtime.run_energyplus(
        state,
        [
            "-w",
            "/Applications/EnergyPlus-25-2-0/WeatherData/USA_CO_Golden-NREL.724666_TMY3.epw",
            "-d",
            "out",
            "test.idf",
        ],
    )
    assert not api.exchange.api_error_flag(state)

    sql_path = Path("out/eplusout.sql")
    assert sql_path.exists(), f"SQL file not found at {sql_path}"
    df = parse_sql(sql_path)
    print(df)
    df.truncate(after="2013-01-03 00:00").plot()
    plt.show()
