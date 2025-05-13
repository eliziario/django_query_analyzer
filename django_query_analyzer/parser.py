# django_query_analyzer/parser.py

import ast
import os
from collections import defaultdict
from typing import Set, Tuple, List, FrozenSet, Dict
import pathspec

ResultKey = Tuple[FrozenSet[str], FrozenSet[str]]  # (filters+excludes, annotates)
Location = Tuple[str, int]  # (file_path, line_number)

DJANGO_LOOKUPS = {
    'exact', 'iexact', 'contains', 'icontains', 'in', 'gt', 'gte', 'lt', 'lte',
    'startswith', 'istartswith', 'endswith', 'iendswith', 'range', 'year', 'month',
    'day', 'week_day', 'hour', 'minute', 'second', 'isnull', 'regex', 'iregex'
}

def resolve_related_field(path: str, fk_map: Dict[str, str]) -> List[str]:
    parts = path.split("__")
    if parts[-1] in DJANGO_LOOKUPS:
        parts = parts[:-1]

    if len(parts) == 1:
        if parts[0] in fk_map:
            return [fk_map[parts[0]]]
        return [parts[0]]

    resolved = []
    for i in range(len(parts) - 1):
        prefix = "__".join(parts[:i + 1])
        full_path = ".".join(parts[:i + 1])
        if prefix in fk_map:
            resolved.append(fk_map[prefix])
        else:
            resolved.append(f"{full_path}_id")

    if parts:
        resolved.append(".".join(parts))
    return resolved


def extract_keywords_from_q(node: ast.AST) -> List[str]:
    result = []
    if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "Q":
        for kw in node.keywords:
            if kw.arg:
                result.append(kw.arg)
    elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.BitOr, ast.BitAnd)):
        result.extend(extract_keywords_from_q(node.left))
        result.extend(extract_keywords_from_q(node.right))
    return result


class QueryAnalyzer(ast.NodeVisitor):
    def __init__(self, target_model: str, ignore_tests: bool = True):
        self.target_model = target_model
        self.ignore_tests = ignore_tests
        self.results: defaultdict[ResultKey, List[Location]] = defaultdict(list)
        self.foreign_keys: Dict[str, str] = {}
        self.current_class_prefix = []

    def visit_ClassDef(self, node: ast.ClassDef):
        self.current_class_prefix.append(node.name)
        for stmt in node.body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        field_name = target.id
                        if isinstance(stmt.value, ast.Call):
                            if isinstance(stmt.value.func, ast.Attribute):
                                if stmt.value.func.attr == "ForeignKey":
                                    current_prefix = "__".join(self.current_class_prefix[:-1])
                                    prefix = f"{current_prefix}__{field_name}" if current_prefix else field_name
                                    full_path = prefix.replace("__", ".")
                                    self.foreign_keys[prefix] = f"{full_path}_id"
                                    self.foreign_keys[field_name] = f"{field_name}_id"
        self.generic_visit(node)
        self.current_class_prefix.pop()

    def visit_Call(self, node: ast.Call):
        filters, annotates = self._extract_queryset_chain_fields(node)
        if filters or annotates:
            key: ResultKey = (frozenset(filters), frozenset(annotates))
            self.results[key].append((self.filepath, node.lineno))
        self.generic_visit(node)

    def _extract_queryset_chain_fields(self, node: ast.Call) -> Tuple[Set[str], Set[str]]:
        filters, annotates = set(), set()
        current = node

        while isinstance(current, ast.Call):
            func = current.func
            if isinstance(func, ast.Attribute):
                method = func.attr
                if method in {"filter", "exclude"}:
                    for kw in current.keywords:
                        if kw.arg:
                            resolved = resolve_related_field(kw.arg, self.foreign_keys)
                            filters.update(resolved)
                    for arg in current.args:
                        for qkey in extract_keywords_from_q(arg):
                            resolved = resolve_related_field(qkey, self.foreign_keys)
                            filters.update(resolved)
                elif method in {"annotate", "aggregate"}:
                    for kw in current.keywords:
                        if isinstance(kw.value, ast.Call):
                            call = kw.value
                            if call.args and isinstance(call.args[0], ast.Str):
                                resolved = resolve_related_field(call.args[0].s, self.foreign_keys)
                                annotates.update(resolved)
                    for arg in current.args:
                        if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name):
                            if arg.args and isinstance(arg.args[0], ast.Str):
                                resolved = resolve_related_field(arg.args[0].s, self.foreign_keys)
                                annotates.update(resolved)
                current = func.value
            else:
                break

        if (
            isinstance(current, ast.Attribute)
            and current.attr == "objects"
            and isinstance(current.value, ast.Name)
            and current.value.id == self.target_model
        ):
            return filters, annotates
        return set(), set()

    def analyze_file(self, filepath: str):
        self.filepath = filepath
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=filepath)
            self.visit(tree)
        except SyntaxError:
            pass

    def _load_gitignore(self, base_dir: str):
        gitignore_path = os.path.join(base_dir, ".gitignore")
        if os.path.exists(gitignore_path):
            with open(gitignore_path, "r") as f:
                return pathspec.PathSpec.from_lines("gitwildmatch", f)
        return pathspec.PathSpec([])

    def scan_directory(self, base_dir: str) -> defaultdict[ResultKey, List[Location]]:
        spec = self._load_gitignore(base_dir)
        for root, dirs, files in os.walk(base_dir):
            rel_root = os.path.relpath(root, base_dir)
            if spec.match_file(rel_root):
                continue
            dirs[:] = [d for d in dirs if not spec.match_file(os.path.join(rel_root, d))]
            for filename in files:
                rel_file = os.path.join(rel_root, filename)
                if filename.endswith(".py") and not spec.match_file(rel_file):
                    if self.ignore_tests and (filename.startswith("test") or "/tests/" in rel_file.replace("\\", "/")):
                        continue
                    full_path = os.path.join(root, filename)
                    self.analyze_file(full_path)
        return self.results
