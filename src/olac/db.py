"""Load every processed CSV into the DuckDB warehouse `raw` schema (one table per file)."""

from __future__ import annotations

import duckdb

from olac.paths import PROCESSED, WAREHOUSE


def run() -> None:
    con = duckdb.connect(str(WAREHOUSE))
    con.execute("create schema if not exists raw")
    n = 0
    for csv in sorted(PROCESSED.glob("*.csv")):
        table = csv.stem
        con.execute(
            f"create or replace table raw.{table} as "
            f"select * from read_csv_auto('{csv.as_posix()}', header=true, sample_size=-1)"
        )
        n += 1
    con.close()
    print(f"loaded {n} tables into {WAREHOUSE.name}:raw")


if __name__ == "__main__":
    run()
