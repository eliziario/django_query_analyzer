# django_query_analyzer/cli.py

import argparse
from django_query_analyzer.parser import QueryAnalyzer
from django_query_analyzer.reporter import report_table, report_json, report_csv, summarize_by_table


def run():
    parser = argparse.ArgumentParser(
        description="Analyze Django ORM usage of filters, excludes, and annotations on a given model."
    )
    parser.add_argument(
        "directory",
        type=str,
        help="Root directory of your Django codebase",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="Record",
        help="Model name to search for (default: Record)",
    )
    parser.add_argument(
        "--output-format",
        type=str,
        choices=["table", "json", "csv"],
        default="table",
        help="Output format: table, json, csv (default: table)",
    )
    parser.add_argument(
        "--csv-file",
        type=str,
        default="query_analysis.csv",
        help="CSV filename if --output-format=csv (default: query_analysis.csv)",
    )
    parser.add_argument(
        "--ignore-tests",
        dest="ignore_tests",
        action="store_true",
        default=True,
        help="Ignore test files and test directories (default: True)",
    )
    parser.add_argument(
        "--no-ignore-tests",
        dest="ignore_tests",
        action="store_false",
        help="Include test files in the analysis",
    )

    args = parser.parse_args()

    analyzer = QueryAnalyzer(target_model=args.model, ignore_tests=args.ignore_tests)
    results = analyzer.scan_directory(args.directory)

    if args.output_format == "table":
        report_table(results)
        # summarize_by_table(results)
    elif args.output_format == "json":
        report_json(results)
    elif args.output_format == "csv":
        report_csv(results, filename=args.csv_file)

if __name__ == '__main__':
    run()
