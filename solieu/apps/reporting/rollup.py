"""Single aggregation entry point for dashboard, Excel, and Word.

SQL computes sum, count, cumulative, and latest.
Python computes ratio, average, percent of plan, and behind-schedule flags.
"""


def rollup(period, *, department_id=None):
    """Return aggregated indicator values for one reporting period."""
    raise NotImplementedError
