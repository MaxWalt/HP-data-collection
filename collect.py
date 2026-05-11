#!/usr/bin/env python3
"""
Collect training session data from Strava and/or intervals.icu.

Usage:
  python collect.py                    # both sources
  python collect.py --source strava
  python collect.py --source intervals
  python collect.py --max 10           # limit to 10 activities (for testing)

Output files in ./output/:
  activities.csv   — one row per session (name, distance, speed, HR, …)
  laps.csv         — one row per lap
  hr_zones.csv     — time spent in each HR zone per session
"""

import csv
import os
import sys
import argparse
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

OUTPUT_DIR = Path("output")

ACTIVITY_FIELDS = [
    "source", "activity_id", "name", "date", "sport_type",
    "distance_m", "moving_time_s", "elapsed_time_s",
    "avg_speed_ms", "max_speed_ms",
    "avg_hr", "max_hr", "elevation_gain_m",
]

LAP_FIELDS = [
    "source", "activity_id", "lap_index", "name",
    "distance_m", "elapsed_time_s", "moving_time_s",
    "avg_speed_ms", "max_speed_ms",
    "avg_hr", "max_hr",
]

ZONE_FIELDS = [
    "source", "activity_id", "zone_index", "zone_label",
    "zone_min_hr", "zone_max_hr", "time_in_zone_s",
]


def _write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Saved {len(rows):,} rows → {path}")


def _require_env(*names):
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        sys.exit(f"Missing environment variables: {', '.join(missing)}\n"
                 f"Copy .env.example to .env and fill in the values.")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", choices=["strava", "intervals", "both"],
                        default="both", help="Data source (default: both)")
    parser.add_argument("--max", type=int, default=None,
                        metavar="N", help="Max activities per source (for quick tests)")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(exist_ok=True)

    all_activities, all_laps, all_zones = [], [], []

    if args.source in ("strava", "both"):
        _require_env("STRAVA_CLIENT_ID", "STRAVA_CLIENT_SECRET", "STRAVA_REFRESH_TOKEN")
        import strava
        acts, laps, zones = strava.collect(
            os.environ["STRAVA_CLIENT_ID"],
            os.environ["STRAVA_CLIENT_SECRET"],
            os.environ["STRAVA_REFRESH_TOKEN"],
            max_activities=args.max,
        )
        all_activities.extend(acts)
        all_laps.extend(laps)
        all_zones.extend(zones)

    if args.source in ("intervals", "both"):
        _require_env("INTERVALS_API_KEY", "INTERVALS_ATHLETE_ID")
        import intervals
        acts, laps, zones = intervals.collect(
            os.environ["INTERVALS_API_KEY"],
            os.environ["INTERVALS_ATHLETE_ID"],
            max_activities=args.max,
        )
        all_activities.extend(acts)
        all_laps.extend(laps)
        all_zones.extend(zones)

    print("\nWriting CSVs...")
    _write_csv(OUTPUT_DIR / "activities.csv", all_activities, ACTIVITY_FIELDS)
    _write_csv(OUTPUT_DIR / "laps.csv", all_laps, LAP_FIELDS)
    _write_csv(OUTPUT_DIR / "hr_zones.csv", all_zones, ZONE_FIELDS)
    print("\nDone. Files are in ./output/")


if __name__ == "__main__":
    main()
