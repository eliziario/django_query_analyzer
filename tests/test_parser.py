# tests/test_parser.py

import ast
from django_query_analyzer.parser import QueryAnalyzer
from collections import defaultdict



def test_q_expression_support(tmp_path):
    code = """
from myapp.models import Record
from django.db import models
from django.db.models import Q

class Client: pass
class Location: pass

class Record:
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    location = models.ForeignKey(Location, on_delete=models.CASCADE)

def run():
    Record.objects.filter(
        Q(client=self.client),
        is_active=True
    )
"""
    file = tmp_path / "q_expression_test.py"
    file.write_text(code)

    analyzer = QueryAnalyzer("Record")
    analyzer.analyze_file(str(file))
    results = analyzer.results
    assert len(results) >= 1
    (filters, annotates), _ = list(results.items())[0]

    assert "client_id" in filters
    assert "is_active" in filters


def test_q_binary_expression_support(tmp_path):
    code = """
from myapp.models import Record
from django.db import models
from django.db.models import Q

class Client: pass
class Location: pass

class Record:
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    location = models.ForeignKey(Location, on_delete=models.CASCADE)

def run():
    Record.objects.filter(
        Q(client=self.client) | Q(location=self.location),
        is_active=True
    )
"""
    file = tmp_path / "q_expression_test.py"
    file.write_text(code)

    analyzer = QueryAnalyzer("Record")
    analyzer.analyze_file(str(file))
    results = analyzer.results
    assert len(results) >= 1
    (filters, annotates), _ = list(results.items())[0]

    assert "client_id" in filters
    assert "location_id" in filters
    assert "is_active" in filters


def test_simple_filter(tmp_path):
    code = """
from myapp.models import Record

def example():
    Record.objects.filter(is_active=True, client_id=1).annotate(foo=Count('x'))
"""
    file = tmp_path / "test_file.py"
    file.write_text(code)

    analyzer = QueryAnalyzer("Record")
    analyzer.analyze_file(str(file))

    results = analyzer.results
    assert len(results) >= 1
    (filters, annotates), locations = list(results.items())[0]
    assert "is_active" in filters
    assert "client_id" in filters
    assert "x" in annotates or "x_id" in annotates


def test_annotate_count_and_fk_resolution(tmp_path):
    code = """
from myapp.models import Record
from django.db import models
from django.db.models import Count

class Team:
    division = models.ForeignKey('Division', on_delete=models.CASCADE)

class Division:
    department = models.ForeignKey('Department', on_delete=models.CASCADE)

class Department:
    pass

class Record:
    team = models.ForeignKey(Team, on_delete=models.CASCADE)

def query():
    return Record.objects.filter(team__division__department__is_active=True).annotate(Count("team"))
"""
    file = tmp_path / "fk_chain_test.py"
    file.write_text(code)

    analyzer = QueryAnalyzer("Record")
    analyzer.analyze_file(str(file))
    results = analyzer.results
    assert len(results) >= 1
    (filters, annotates), _ = list(results.items())[0]

    assert "team_id" in filters
    assert "team.division_id" in filters
    assert "team.division.department_id" in filters
    assert "team.division.department.is_active" in filters
    assert "team_id" in annotates or "team" in annotates


def test_chained_filter_and_exclude(tmp_path):
    code = """
from myapp.models import Record
from django.db.models import Count

def get_teams(start, end):
    return Record.objects.filter(
        team__is_active=True,
        is_active=True,
        session__removed=False,
        session__start__gte=start,
        session__end__lte=end,
        locked=False,
    ).exclude(
        team__division__department__is_active=False
    ).values_list("team_id", flat=True).distinct()
"""
    file = tmp_path / "exclude_test.py"
    file.write_text(code)

    analyzer = QueryAnalyzer("Record")
    analyzer.analyze_file(str(file))
    results = analyzer.results
    assert len(results) >= 1
    filters, _ = list(results.keys())[0]

    assert "session_id" in filters
    assert "session.start" in filters
    assert "session.end" in filters
    assert "session.removed" in filters
    assert "team_id" in filters
    assert "team.division_id" in filters
    assert "team.division.department_id" in filters
    assert "team.division.department.is_active" in filters
    assert "is_active" in filters
    assert "locked" in filters


def test_direct_fk_fields(tmp_path):
    code = """
from myapp.models import Record
from django.db import models

class Client: pass
class Location: pass
class Appointment: pass

class Record:
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    location = models.ForeignKey(Location, on_delete=models.CASCADE)
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE)

def run():
    Record.objects.filter(
        appointment=self.appointment,
        location=self.location,
        client=self.client,
        is_active=True,
    )
"""
    file = tmp_path / "direct_fk_test.py"
    file.write_text(code)

    analyzer = QueryAnalyzer("Record")
    analyzer.analyze_file(str(file))
    results = analyzer.results
    assert len(results) >= 1
    (filters, annotates), _ = list(results.items())[0]

    assert "appointment_id" in filters
    assert "location_id" in filters
    assert "client_id" in filters
    assert "is_active" in filters

def test_aggregate_support(tmp_path):
    code = """
from myapp.models import Record
from django.db import models
from django.db.models import Sum, Avg, Max, Min

class Transaction:
    amount = models.DecimalField(max_digits=10, decimal_places=2)

class Record:
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE)

def run():
    Record.objects.aggregate(
        Sum("transaction__amount"),
        Avg("transaction__amount"),
        Max("transaction__amount"),
        Min("transaction__amount")
    )
"""
    file = tmp_path / "agg_test.py"
    file.write_text(code)

    analyzer = QueryAnalyzer("Record")
    analyzer.analyze_file(str(file))
    results = analyzer.results
    assert len(results) >= 1
    (_, annotates), _ = list(results.items())[0]

    assert "transaction_id" in annotates
    assert "transaction.amount" in annotates

def test_aggregate_support_kw(tmp_path):
    code = """
from myapp.models import Record
from django.db import models
from django.db.models import Sum, Avg, Max, Min

class Transaction:
    amount = models.DecimalField(max_digits=10, decimal_places=2)

class Record:
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE)

def run():
    Record.objects.aggregate(
        total_sum=Sum("transaction__amount"),
        avg_amount=Avg("transaction__amount"),
        max_amount=Max("transaction__amount"),
        min_amount=Min("transaction__amount")
    )
"""
    file = tmp_path / "agg_test.py"
    file.write_text(code)

    analyzer = QueryAnalyzer("Record")
    analyzer.analyze_file(str(file))
    results = analyzer.results
    assert len(results) >= 1
    (_, annotates), _ = list(results.items())[0]

    assert "transaction_id" in annotates
    assert "transaction.amount" in annotates
