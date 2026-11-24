"""Execute the SQL analysis file and print every result table.

Usage: python -m zakbench.analysis.query --dir zakbench/results/parquet/suite-9
"""
import argparse
import os
from pathlib import Path

import duckdb


def analyze(folder: Path):
    folder = Path(folder).resolve()
    for filename in ("suite_runs.parquet", "runs.parquet", "attempts.parquet"):
        if not (folder / filename).is_file():
            raise FileNotFoundError(folder / filename)

    # The SQL intentionally uses paths relative to its exported suite folder.
    previous = Path.cwd()
    con = duckdb.connect(":memory:")
    try:
        os.chdir(folder)
        con.execute(Path(__file__).with_name("queries.sql").read_text(encoding="utf-8"))
        for label, sql in (
            ("PER-LANGUAGE METRICS", "SELECT * FROM language_metrics ORDER BY language"),
            ("CATEGORY METRICS", "SELECT * FROM category_metrics ORDER BY category, language"),
            ("PAIRED ZAK/PYTHON METRICS", "SELECT * FROM paired_metrics"),
            ("ATTEMPT COUNTS", """
                SELECT r.language, COUNT(*) AS attempts
                FROM exported_attempts a
                JOIN exported_runs r ON r.run_id = a.run_id
                GROUP BY r.language ORDER BY r.language
            """),
        ):
            cursor = con.execute(sql)
            columns = [col[0] for col in cursor.description]
            print(f"\n{label}")
            print(" | ".join(columns))
            for row in cursor.fetchall():
                print(" | ".join("NULL" if value is None else str(value) for value in row))
    finally:
        os.chdir(previous)
        con.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, required=True)
    args = parser.parse_args(argv)
    analyze(args.dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
