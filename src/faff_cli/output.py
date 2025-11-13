"""
Unified output formatting for Faff CLI.

Provides consistent output modes across all commands:
- Rich formatting (default) - human-readable with colors and tables
- JSON output (--json) - machine-readable
- Plain text (--plain) - for piping and scripting
"""

import json
import sys
from typing import Any, Dict, List, Optional, Sequence
from rich.console import Console
from rich.table import Table


class OutputFormatter:
    """Handles output formatting in Rich, JSON, or plain text modes."""

    def __init__(self, json_mode: bool = False, plain_mode: bool = False):
        """
        Initialize the formatter.

        Args:
            json_mode: Output as JSON
            plain_mode: Output as plain text (no colors)
        """
        self.json_mode = json_mode
        self.plain_mode = plain_mode
        self.console = Console() if not plain_mode else Console(highlight=False, color_system=None)

    def print_table(
        self,
        data: List[Dict[str, Any]],
        columns: Sequence[tuple[str, str, Optional[str]]],  # (key, title, style)
        title: Optional[str] = None,
        total_label: Optional[str] = None,
    ):
        """
        Print data as a table.

        Args:
            data: List of dictionaries containing row data
            columns: List of (dict_key, column_title, style) tuples
            title: Optional table title
            total_label: If provided, add a footer with this label and count
        """
        if self.json_mode:
            self._print_json({
                "items": data,
                "total": len(data)
            })
        elif self.plain_mode:
            self._print_plain_table(data, columns)
        else:
            self._print_rich_table(data, columns, title, total_label)

    def print_list(
        self,
        items: List[str],
        total_label: Optional[str] = None,
    ):
        """
        Print a simple list of items.

        Args:
            items: List of strings to display
            total_label: If provided, add a footer with this label and count
        """
        if self.json_mode:
            self._print_json({
                "items": items,
                "total": len(items)
            })
        elif self.plain_mode:
            for item in items:
                print(item)
            if total_label:
                print(f"\n{total_label}: {len(items)}")
        else:
            for item in items:
                self.console.print(item)
            if total_label:
                self.console.print(f"\n[bold]{total_label}:[/bold] {len(items)}")

    def print_detail(
        self,
        data: Dict[str, Any],
        sections: Optional[List[tuple[str, List[tuple[str, str]]]]] = None,
    ):
        """
        Print detailed view of a single item.

        Args:
            data: Dictionary of item data
            sections: Optional list of (section_title, [(label, key)]) tuples
        """
        if self.json_mode:
            self._print_json(data)
        elif self.plain_mode:
            self._print_plain_detail(data, sections)
        else:
            self._print_rich_detail(data, sections)

    def print_message(self, message: str, style: str = ""):
        """
        Print a simple message.

        Args:
            message: The message to print
            style: Rich style markup (ignored in plain/JSON modes)
        """
        if self.json_mode:
            return  # Don't print messages in JSON mode
        elif self.plain_mode:
            print(message)
        else:
            if style:
                self.console.print(f"[{style}]{message}[/{style}]")
            else:
                self.console.print(message)

    def print_success(self, message: str):
        """Print a success message with checkmark."""
        if not self.json_mode:
            formatted = f"✓ {message}" if not message.startswith("✓") else message
            if self.plain_mode:
                print(formatted)
            else:
                self.console.print(f"[green]{formatted}[/green]")

    def print_error(self, message: str):
        """Print an error message to stderr."""
        if not self.json_mode:
            formatted = f"Error: {message}" if not message.startswith("Error:") else message
            print(formatted, file=sys.stderr)

    def print_warning(self, message: str):
        """Print a warning message to stderr."""
        if not self.json_mode:
            formatted = f"Warning: {message}" if not message.startswith("Warning:") else message
            if self.plain_mode:
                print(formatted, file=sys.stderr)
            else:
                # Rich Console doesn't support file parameter, use stderr console
                from rich.console import Console
                stderr_console = Console(stderr=True)
                stderr_console.print(f"[yellow]{formatted}[/yellow]")

    # Private methods

    def _print_json(self, data: Any):
        """Print data as JSON to stdout."""
        print(json.dumps(data, indent=2, default=str))

    def _print_rich_table(
        self,
        data: List[Dict[str, Any]],
        columns: Sequence[tuple[str, str, Optional[str]]],
        title: Optional[str],
        total_label: Optional[str],
    ):
        """Print data as Rich table."""
        table = Table(title=title, show_header=True, header_style="bold")

        # Add columns
        for _, col_title, style in columns:
            table.add_column(col_title, style=style or None)

        # Add rows
        for row in data:
            values = []
            for key, _, _ in columns:
                value = row.get(key, "")
                # Convert to string, handling None
                values.append(str(value) if value is not None else "")
            table.add_row(*values)

        self.console.print(table)

        # Print count
        if total_label:
            self.console.print(f"\n[bold]Total:[/bold] {len(data)} {total_label.lower()}")

    def _print_plain_table(
        self,
        data: List[Dict[str, Any]],
        columns: Sequence[tuple[str, str, Optional[str]]],
    ):
        """Print data as tab-separated plain text."""
        # Print header
        headers = [col_title for _, col_title, _ in columns]
        print("\t".join(headers))

        # Print rows
        for row in data:
            values = []
            for key, _, _ in columns:
                value = row.get(key, "")
                values.append(str(value) if value is not None else "")
            print("\t".join(values))

    def _print_rich_detail(
        self,
        data: Dict[str, Any],
        sections: Optional[List[tuple[str, List[tuple[str, str]]]]],
    ):
        """Print detailed view with Rich formatting."""
        if sections:
            for section_title, fields in sections:
                self.console.print(f"\n[bold]{section_title}[/bold]")
                for label, key in fields:
                    value = data.get(key, "")
                    self.console.print(f"  [dim]{label}:[/dim] {value}")
        else:
            # No sections defined, just print all fields
            for key, value in data.items():
                self.console.print(f"[bold]{key}:[/bold] {value}")

    def _print_plain_detail(
        self,
        data: Dict[str, Any],
        sections: Optional[List[tuple[str, List[tuple[str, str]]]]],
    ):
        """Print detailed view as plain text."""
        if sections:
            for section_title, fields in sections:
                print(f"\n{section_title}")
                for label, key in fields:
                    value = data.get(key, "")
                    print(f"  {label}: {value}")
        else:
            for key, value in data.items():
                print(f"{key}: {value}")


def create_formatter(json_output: bool = False, plain_output: bool = False) -> OutputFormatter:
    """
    Create an OutputFormatter with the specified modes.

    Args:
        json_output: Enable JSON output mode
        plain_output: Enable plain text output mode

    Returns:
        Configured OutputFormatter instance
    """
    return OutputFormatter(json_mode=json_output, plain_mode=plain_output)
