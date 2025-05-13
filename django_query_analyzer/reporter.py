# django_query_analyzer/reporter.py

import json
import csv
from collections import defaultdict
from typing import FrozenSet, List, Tuple, Dict

ResultKey = Tuple[FrozenSet[str], FrozenSet[str]]
Location = Tuple[str, int]


def report_table(results: defaultdict[ResultKey, List[Location]]):
    print(f"{'Filter/Exclude Fields':<60} | {'Annotate Fields':<40} | Frequency | Locations")
    print("-" * 130)
    for (filters, annotates), locations in sorted(results.items(), key=lambda x: len(x[1]), reverse=True):
        filter_list = ", ".join(sorted(filters)) or "-"
        annotate_list = ", ".join(sorted(annotates)) or "-"
        print(f"{filter_list:<60} | {annotate_list:<40} | {len(locations):>9} |")
        for path, line in locations:
            print(f"{'':<110} ↳ {path}:{line}")
        print()


def report_json(results: defaultdict[ResultKey, List[Location]]):
    output = {}
    for (filters, annotates), locations in results.items():
        key = f"filters={tuple(sorted(filters))}, annotates={tuple(sorted(annotates))}"
        output[key] = [{"file": f, "line": l} for f, l in locations]
    print(json.dumps(output, indent=2))


def report_csv(results: defaultdict[ResultKey, List[Location]], filename="query_analysis.csv"):
    with open(filename, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Filter Fields", "Annotate Fields", "Frequency", "File", "Line"])
        for (filters, annotates), locations in results.items():
            for file, line in locations:
                writer.writerow([
                    ", ".join(sorted(filters)),
                    ", ".join(sorted(annotates)),
                    len(locations),
                    file,
                    line
                ])


def summarize_by_table(results: defaultdict[ResultKey, List[Location]]):
    table_usage: Dict[str, Set[str]] = defaultdict(set)
    for (filters, annotates), _ in results.items():
        all_fields = filters.union(annotates)
        for field in all_fields:
            if "." in field:
                parts = field.split(".")
                prefix = "main"
                for i in range(len(parts) - 1):
                    parent_path = ".".join(parts[:i + 1])
                    table_usage[prefix].add(f"{parts[i]}_id")
                    prefix = parent_path
                table_usage[prefix].add(parts[-1])
            else:
                table_usage["main"].add(field)

    print("\n📊 Suggested Index Coverage by Table")
    print("-" * 40)
    for table, fields in sorted(table_usage.items()):
        print(f"{table}: {', '.join(sorted(fields))}")
