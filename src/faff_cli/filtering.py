"""
Unified filtering for Faff CLI.

Provides consistent filtering capabilities across all list/query commands:
- Filter syntax: field=value, field~value, field!=value
- Date range handling: --from, --to, --since, --until
- Filter validation and error messages
"""

import datetime
from typing import List, Optional, Tuple
import typer
from faff_core import Workspace, Filter


class FilterConfig:
    """Configuration for filtering command line arguments."""

    def __init__(
        self,
        filter_strings: Optional[List[str]] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
    ):
        """
        Initialize filter configuration.

        Args:
            filter_strings: List of filter strings (e.g., ["role=engineer", "objective~revenue"])
            from_date: Start date string (inclusive)
            to_date: End date string (inclusive)
            since: Shortcut for --from with open end
            until: Shortcut for --to with open start
        """
        self.filter_strings = filter_strings or []
        self.from_date = from_date
        self.to_date = to_date
        self.since = since
        self.until = until

    def validate(self):
        """
        Validate filter configuration for mutually exclusive options.

        Raises:
            typer.Exit: If validation fails
        """
        if self.from_date and self.since:
            typer.echo("Error: --from and --since are mutually exclusive.", err=True)
            raise typer.Exit(1)

        if self.to_date and self.until:
            typer.echo("Error: --to and --until are mutually exclusive.", err=True)
            raise typer.Exit(1)

    def parse_filters(self) -> List[Filter]:
        """
        Parse filter strings into Filter objects.

        Returns:
            List of parsed Filter objects

        Raises:
            typer.Exit: If filter parsing fails
        """
        filters = []
        for filter_str in self.filter_strings:
            try:
                filters.append(Filter.parse(filter_str))
            except Exception as e:
                typer.echo(
                    f"Error: Invalid filter '{filter_str}': {e}\n"
                    f"Valid formats: field=value, field~value, field!=value",
                    err=True
                )
                raise typer.Exit(1)
        return filters

    def parse_dates(self, ws: Workspace) -> Tuple[Optional[datetime.date], Optional[datetime.date]]:
        """
        Parse and resolve date strings.

        Args:
            ws: Workspace instance for date parsing

        Returns:
            Tuple of (from_date, to_date) as date objects (or None)

        Raises:
            typer.Exit: If date parsing fails
        """
        # Resolve which date strings to use
        start_date_str = self.from_date or self.since
        end_date_str = self.to_date or self.until

        # Parse dates
        from_date = None
        to_date = None

        if start_date_str:
            try:
                from_date = ws.parse_natural_date(start_date_str)
            except Exception as e:
                typer.echo(f"Error: Invalid start date '{start_date_str}': {e}", err=True)
                raise typer.Exit(1)

        if end_date_str:
            try:
                to_date = ws.parse_natural_date(end_date_str)
            except Exception as e:
                typer.echo(f"Error: Invalid end date '{end_date_str}': {e}", err=True)
                raise typer.Exit(1)

        # Validate date range
        if from_date and to_date and from_date > to_date:
            typer.echo(
                f"Error: Start date ({from_date}) is after end date ({to_date}).",
                err=True
            )
            raise typer.Exit(1)

        return from_date, to_date

    def get_all(self, ws: Workspace) -> Tuple[List[Filter], Optional[datetime.date], Optional[datetime.date]]:
        """
        Validate and parse all filter configuration.

        Args:
            ws: Workspace instance for date parsing

        Returns:
            Tuple of (filters, from_date, to_date)

        Raises:
            typer.Exit: If validation or parsing fails
        """
        self.validate()
        filters = self.parse_filters()
        from_date, to_date = self.parse_dates(ws)
        return filters, from_date, to_date


# Note: The create_filter_arguments() function was removed as typer doesn't support
# argument unpacking the way we initially designed. Instead, commands should directly
# define their arguments following the patterns shown in the guidelines.


class SimpleFilter:
    """Simple Python-only filter for display purposes (no Rust validation)."""
    def __init__(self, field: str, operator: str, value: str):
        self._field = field
        self._operator = operator
        self._value = value

    def field(self) -> str:
        return self._field

    def operator(self) -> str:
        return self._operator

    def value(self) -> str:
        return self._value


def parse_simple_filters(filter_strings: List[str]) -> List[SimpleFilter]:
    """
    Parse filter strings into SimpleFilter objects (Python-only, no Rust validation).

    Args:
        filter_strings: List of filter strings

    Returns:
        List of SimpleFilter objects

    Raises:
        ValueError: If any filter string is invalid
    """
    filters = []
    for filter_str in filter_strings:
        if "!=" in filter_str:
            parts = filter_str.split("!=", 1)
            if len(parts) != 2:
                raise ValueError(f"Invalid filter format: {filter_str}")
            filters.append(SimpleFilter(parts[0].strip(), "!=", parts[1].strip()))
        elif "=" in filter_str:
            parts = filter_str.split("=", 1)
            if len(parts) != 2:
                raise ValueError(f"Invalid filter format: {filter_str}")
            filters.append(SimpleFilter(parts[0].strip(), "=", parts[1].strip()))
        elif "~" in filter_str:
            parts = filter_str.split("~", 1)
            if len(parts) != 2:
                raise ValueError(f"Invalid filter format: {filter_str}")
            filters.append(SimpleFilter(parts[0].strip(), "~", parts[1].strip()))
        else:
            raise ValueError(f"Invalid filter format: {filter_str}. Must contain =, ~, or !=")
    return filters


def apply_filters(items: List[dict], filters: List[Filter]) -> List[dict]:
    """
    Apply filters to a list of dictionaries.

    Args:
        items: List of dictionaries to filter
        filters: List of Filter objects to apply (AND logic)

    Returns:
        Filtered list of items
    """
    filtered_items = []

    for item in items:
        # Check all filters (AND logic)
        if all(matches_filter(item, f) for f in filters):
            filtered_items.append(item)

    return filtered_items


def matches_filter(item: dict, filter_obj: Filter) -> bool:
    """
    Check if an item matches a single filter.

    Args:
        item: Dictionary to check
        filter_obj: Filter to apply

    Returns:
        True if item matches the filter
    """
    field = filter_obj.field()
    value = item.get(field, "")
    filter_value = filter_obj.value()
    operator = filter_obj.operator()

    # Convert to string for comparison (handles None gracefully)
    value_str = str(value) if value is not None else ""

    if operator == "=":
        return value_str == filter_value
    elif operator == "~":
        return filter_value.lower() in value_str.lower()
    elif operator == "!=":
        return value_str != filter_value

    return True


def apply_date_range(
    items: List[dict],
    date_field: str,
    from_date: Optional[datetime.date],
    to_date: Optional[datetime.date],
) -> List[dict]:
    """
    Filter items by date range.

    Args:
        items: List of dictionaries to filter
        date_field: Name of the date field in each dictionary
        from_date: Start date (inclusive, None for no start limit)
        to_date: End date (inclusive, None for no end limit)

    Returns:
        Filtered list of items within date range
    """
    if not from_date and not to_date:
        return items

    filtered_items = []

    for item in items:
        item_date = item.get(date_field)

        # Skip items without the date field
        if item_date is None:
            continue

        # Convert to date if needed
        if isinstance(item_date, str):
            try:
                item_date = datetime.date.fromisoformat(item_date)
            except ValueError:
                continue
        elif isinstance(item_date, datetime.datetime):
            item_date = item_date.date()

        # Check date range
        if from_date and item_date < from_date:
            continue
        if to_date and item_date > to_date:
            continue

        filtered_items.append(item)

    return filtered_items
