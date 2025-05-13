# README.md

# record-query-analysis

**record-query-analysis** is a command-line tool for analyzing Django ORM usage of `.filter()`, `.exclude()`, and `.annotate()` on a specific model across a Python codebase.

## 🔍 Features
- Detects chained querysets on a target model (e.g., `Record.objects.filter(...).annotate(...)`)
- Extracts used fields in `filter`, `exclude`, and `annotate`
- Aggregates and counts unique field combinations
- Outputs results in **table**, **JSON**, or **CSV** formats

## 🚀 Installation
```bash
pip install -e .  # or build via uv, poetry, etc.
```

## 🧪 Usage
```bash
record-query-analysis path/to/your/codebase --model=Record --output-format=table
```

### Options:
- `--model`: Django model name (default: `Record`)
- `--output-format`: `table` (default), `json`, or `csv`
- `--csv-file`: custom file path for CSV output

## 📦 Example Output
```text
Filter/Exclude Fields                  | Annotate Fields           | Frequency | Locations
-----------------------------------------------------------------------------------------------
is_active, location_id                | client                    |        12 |
                                                                ↳ app/views/reports.py:45
```

## 📄 License
MIT License
