"""
csv_time_summary.py

Walks a given folder (including all sub-folders) using the `os` module,
finds every .csv file, extracts:
    Start Date, Start Time, Stop Date, Stop Time, Project
from each row, calculates the duration, and produces:

  1. Total time per DATE (across all projects combined)
  2. Total time per DATE broken down by PROJECT
  3. A bar chart (.png) for each date showing time spent per project
  4. A CSV file for each date showing the project breakdown for that date
  5. An overall summary CSV covering every date/project combination

ASSUMPTIONS (adjust the CONFIG section below to match your real files):
  - Each CSV has a header row containing these columns (case-insensitive,
    spaces/underscores are normalized automatically):
        Start Date, Start Time, Stop Date, Stop Time, Project
  - Dates are in a common format like "2024-01-15" or "01/15/2024".
  - Times are in a common format like "09:30:00" or "09:30 AM".
  - A file can have multiple rows (multiple sessions/entries).
  - If a row has no "Project" value, it is grouped under "Unspecified".

If your column names or formats differ, just update COLUMN_ALIASES and
DATE_FORMATS / TIME_FORMATS below -- no other code changes needed.
"""

import os
import csv
from datetime import datetime, timedelta
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")  # render to file, no GUI needed
import matplotlib.pyplot as plt

# ------------------------- CONFIG ------------------------- #

# Default folder to scan if the user just presses Enter at the prompt
DEFAULT_ROOT_FOLDER = r"./data"

# Where to write the overall summary CSV (set to None to skip)
OUTPUT_CSV = r"./total_time_per_date.csv"

# Folder where per-date CSVs and per-date plots are saved
OUTPUT_DIR = r"./output"

# Recognized header names for each required field (lowercase, no spaces/underscores)
COLUMN_ALIASES = {
    "startdate": "start_date",
    "start_date": "start_date",
    "starttime": "start_time",
    "start_time": "start_time",
    "stopdate": "end_date",
    "stop_date": "end_date",
    "enddate": "end_date",       # kept as a fallback alias
    "end_date": "end_date",
    "stoptime": "end_time",
    "stop_time": "end_time",
    "endtime": "end_time",       # kept as a fallback alias
    "end_time": "end_time",
    "project": "project",
}

# Fields that MUST be present in a CSV for it to be processed
REQUIRED_FIELDS = {"start_date", "start_time", "end_date", "end_time"}

# Label used when a row has no Project value
UNSPECIFIED_PROJECT = "Unspecified"

# Try these date formats, in order, until one parses successfully
DATE_FORMATS = [
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%m-%d-%Y",
    "%d %b %Y",
    "%B %d, %Y",
]

# Try these time formats, in order, until one parses successfully
TIME_FORMATS = [
    "%H:%M:%S",
    "%H:%M",
    "%I:%M:%S %p",
    "%I:%M %p",
]

# ------------------------------------------------------------ #


def normalize_header(header):
    """Lowercase and strip spaces/underscores so 'Stop Date', 'stop_date',
    'StopDate' all map to the same key."""
    return header.strip().lower().replace(" ", "").replace("_", "")


def parse_date(value):
    """Try each known date format until one works."""
    value = value.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date format: '{value}'")


def parse_time(value):
    """Try each known time format until one works."""
    value = value.strip()
    for fmt in TIME_FORMATS:
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"Unrecognized time format: '{value}'")


def find_csv_files(root_folder):
    """Walk root_folder and all sub-folders, yielding full paths to .csv files."""
    csv_paths = []
    for dirpath, _dirnames, filenames in os.walk(root_folder):
        for filename in filenames:
            if filename.lower().endswith(".csv"):
                csv_paths.append(os.path.join(dirpath, filename))
    return csv_paths


def map_row_columns(fieldnames):
    """Build a mapping from the file's actual header names to our standard
    keys (start_date, start_time, end_date, end_time, project)."""
    mapping = {}
    for original in fieldnames:
        key = normalize_header(original)
        if key in COLUMN_ALIASES:
            mapping[COLUMN_ALIASES[key]] = original
    return mapping


def extract_rows(csv_path):
    """Read one CSV and yield (start_date, start_datetime, end_datetime, project)
    for every row that has all required fields present and parseable."""
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return

        mapping = map_row_columns(reader.fieldnames)
        if not REQUIRED_FIELDS.issubset(mapping.keys()):
            missing = REQUIRED_FIELDS - mapping.keys()
            print(f"  [SKIP FILE] {csv_path} -- missing columns: {sorted(missing)}")
            return

        has_project_column = "project" in mapping

        for row_num, row in enumerate(reader, start=2):  # header is line 1
            try:
                s_date_raw = row[mapping["start_date"]]
                s_time_raw = row[mapping["start_time"]]
                e_date_raw = row[mapping["end_date"]]
                e_time_raw = row[mapping["end_time"]]

                if not all([s_date_raw, s_time_raw, e_date_raw, e_time_raw]):
                    continue  # blank row / incomplete entry -- skip silently

                s_date = parse_date(s_date_raw)
                s_time = parse_time(s_time_raw)
                e_date = parse_date(e_date_raw)
                e_time = parse_time(e_time_raw)

                start_dt = datetime.combine(s_date, s_time)
                end_dt = datetime.combine(e_date, e_time)

                if end_dt < start_dt:
                    # Handles sessions that cross midnight, e.g. 23:00 -> 01:00
                    end_dt += timedelta(days=1)

                project = row[mapping["project"]].strip() if has_project_column else ""
                project = project if project else UNSPECIFIED_PROJECT

                yield s_date, start_dt, end_dt, project

            except ValueError as e:
                print(f"  [SKIP ROW] {csv_path} row {row_num}: {e}")
                continue


def format_timedelta(td):
    """Format a timedelta as HH:MM:SS (handles >24h totals correctly)."""
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def get_root_folder_from_user():
    """Ask the user for the folder containing the CSV logs. Keeps asking
    until a valid, existing directory is provided (or the default is used)."""
    while True:
        user_input = input(
            f"Enter the log folder path to scan [default: {DEFAULT_ROOT_FOLDER}]: "
        ).strip().strip('"').strip("'")  # strip quotes in case path was pasted with them

        folder = user_input if user_input else DEFAULT_ROOT_FOLDER

        if os.path.isdir(folder):
            return folder

        print(f"  '{folder}' is not a valid folder. Please try again.\n")


def make_plot_for_date(date_key, project_totals, output_dir):
    """Create and save a bar chart of hours spent per project for one date."""
    projects = sorted(project_totals.keys())
    hours = [project_totals[p].total_seconds() / 3600 for p in projects]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(projects, hours, color="#4C72B0")

    ax.set_title(f"Time Spent per Project — {date_key.isoformat()}")
    ax.set_xlabel("Project")
    ax.set_ylabel("Hours")
    ax.set_xticks(range(len(projects)))
    ax.set_xticklabels(projects, rotation=30, ha="right")

    # Label each bar with its exact HH:MM:SS value
    for bar, project in zip(bars, projects):
        label = format_timedelta(project_totals[project])
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            label,
            ha="center",
            va="bottom",
            fontsize=8,
        )

    fig.tight_layout()

    plots_dir = os.path.join(output_dir, "plots")
    os.makedirs(plots_dir, exist_ok=True)
    plot_path = os.path.join(plots_dir, f"{date_key.isoformat()}.png")
    fig.savefig(plot_path, dpi=150)
    plt.close(fig)
    return plot_path


def write_data_for_date(date_key, project_totals, output_dir):
    """Write a CSV with the project breakdown for one date."""
    data_dir = os.path.join(output_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    data_path = os.path.join(data_dir, f"{date_key.isoformat()}.csv")

    date_total = sum(project_totals.values(), timedelta())

    with open(data_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Project", "Total Time (HH:MM:SS)", "Total Seconds"])
        for project in sorted(project_totals.keys()):
            duration = project_totals[project]
            writer.writerow([project, format_timedelta(duration), int(duration.total_seconds())])
        writer.writerow(["TOTAL", format_timedelta(date_total), int(date_total.total_seconds())])

    return data_path


def main():
    root_folder = get_root_folder_from_user()

    print(f"\nScanning '{root_folder}' for CSV files...\n")
    csv_files = find_csv_files(root_folder)

    if not csv_files:
        print("No CSV files found.")
        return

    print(f"Found {len(csv_files)} CSV file(s):")
    for path in csv_files:
        print(f"  - {path}")
    print()

    # totals_by_date[date] = timedelta                  -> total across all projects
    # totals_by_date_project[date][project] = timedelta -> per-project breakdown
    totals_by_date = defaultdict(timedelta)
    totals_by_date_project = defaultdict(lambda: defaultdict(timedelta))
    total_rows_processed = 0

    for csv_path in csv_files:
        for start_date, start_dt, end_dt, project in extract_rows(csv_path):
            duration = end_dt - start_dt
            totals_by_date[start_date] += duration
            totals_by_date_project[start_date][project] += duration
            total_rows_processed += 1

    if not totals_by_date:
        print("No valid start/end date-time entries were found in any file.")
        return

    print(f"\nProcessed {total_rows_processed} valid entries across {len(csv_files)} file(s).\n")

    # ---- Console summary: total per date ---- #
    print(f"{'Date':<12} {'Total Time (HH:MM:SS)':<22}")
    print("-" * 34)
    grand_total = timedelta()
    for date_key in sorted(totals_by_date.keys()):
        duration = totals_by_date[date_key]
        grand_total += duration
        print(f"{date_key.isoformat():<12} {format_timedelta(duration):<22}")
    print("-" * 34)
    print(f"{'GRAND TOTAL':<12} {format_timedelta(grand_total):<22}")

    # ---- Console summary: per date, per project ---- #
    print("\nBreakdown by Project per Date:")
    for date_key in sorted(totals_by_date_project.keys()):
        print(f"\n  {date_key.isoformat()}:")
        for project in sorted(totals_by_date_project[date_key].keys()):
            duration = totals_by_date_project[date_key][project]
            print(f"    {project:<20} {format_timedelta(duration)}")

    # ---- Overall summary CSV (date, project, time) ---- #
    if OUTPUT_CSV:
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Date", "Project", "Total Time (HH:MM:SS)", "Total Seconds"])
            for date_key in sorted(totals_by_date_project.keys()):
                for project in sorted(totals_by_date_project[date_key].keys()):
                    duration = totals_by_date_project[date_key][project]
                    writer.writerow([date_key.isoformat(), project, format_timedelta(duration), int(duration.total_seconds())])
                date_total = totals_by_date[date_key]
                writer.writerow([date_key.isoformat(), "TOTAL", format_timedelta(date_total), int(date_total.total_seconds())])
            writer.writerow(["", "GRAND TOTAL", format_timedelta(grand_total), int(grand_total.total_seconds())])
        print(f"\nOverall summary written to: {OUTPUT_CSV}")

    # ---- Per-date CSV + plot ---- #
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"\nGenerating per-date plots and data files in '{OUTPUT_DIR}'...")
    for date_key in sorted(totals_by_date_project.keys()):
        project_totals = totals_by_date_project[date_key]
        data_path = write_data_for_date(date_key, project_totals, OUTPUT_DIR)
        plot_path = make_plot_for_date(date_key, project_totals, OUTPUT_DIR)
        print(f"  {date_key.isoformat()} -> data: {data_path} | plot: {plot_path}")


if __name__ == "__main__":
    main()
