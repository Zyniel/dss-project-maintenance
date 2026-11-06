"""What a macro shows in its HTML recap.

Each macro fills a RecapPage. recap/html.py lays it out the same way for every macro:

1. the context: macro, project, who ran it and when;
2. the banners of the macro, the notices of the run and the result of the recap dataset, sorted by tone;
3. the figures (metrics);
4. the sections, such as the options and the tags;
5. the table, interactive in DSS.
"""

from typing import Any, NamedTuple

# Colours of statuses, figures, chips and banners.
TONE_SUCCESS = "success"  # Green.
TONE_DANGER = "danger"  # Red.
TONE_PENDING = "pending"  # Blue.
TONE_CAUTION = "caution"  # Amber.
TONE_MUTED = "muted"  # Grey.

# Icons shown before a status.
ICON_CHECK = "check"
ICON_CROSS = "cross"
ICON_CLOCK = "clock"
ICON_WARNING = "warning"
ICON_MINUS = "minus"
ICON_CIRCLE = "circle"

# Kinds of table columns.
COLUMN_TEXT = "text"  # Text on one line.
COLUMN_LONG_TEXT = "long_text"  # Text that wraps.
COLUMN_STATUS = "status"  # A status code, shown with its icon and label.
COLUMN_TAGS = "tags"  # A list of texts, shown as chips.
COLUMN_NUMBER = "number"  # A number, right aligned. None shows nothing.

# The status of the figure that shows every row of the table again.
ALL_STATUSES = "ALL"

# The outcome of a run, set by the runner. DSS itself only shows a success or a failure.
OUTCOME_SUCCESS = "SUCCESS"  # Nothing went wrong.
OUTCOME_WARNING = "WARNING"  # Something went wrong, and the run went on.
OUTCOME_FAILED = "FAILED"  # Something went wrong, and the form asked to fail the run.


class Banner(NamedTuple):
    """A message above the figures: a short title in bold, then a text.

    It gives counts for what the recap dataset holds, and details only for what the recap dataset cannot
    give, such as an error of DSS or a tag of the form: a message must not grow with the project.
    """

    # TONE_PENDING (blue): how to read the run. TONE_DANGER (red): data failed, or a real run would stop.
    # TONE_CAUTION (yellow): what to check. TONE_MUTED (grey): for information.
    tone: str
    title: str
    text: str = ""

    def __str__(self) -> str:
        """Return the whole message, for the JSON recap and the log."""
        return f"{self.title} {self.text}".strip()


class Metric(NamedTuple):
    """A headline figure. With a status, clicking it shows only the rows of that status in the table."""

    label: str
    value: str
    tone: str = ""
    status: str = ""  # A status code, or ALL_STATUSES.


class Chip(NamedTuple):
    """A short text in a grey box, such as an option and its value. TONE_CAUTION makes it stand out."""

    text: str
    tone: str = ""


class Section(NamedTuple):
    """A titled block of chips or text. The note follows the title, not in bold."""

    title: str
    note: str = ""
    chips: tuple[Chip, ...] = ()
    text: str = ""


class Status(NamedTuple):
    """A status of a table row."""

    code: str  # As stored in the row, the JSON recap and the recap dataset.
    label: str  # As shown, and as exported to CSV.
    tone: str
    icon: str


class Column(NamedTuple):
    """A column of the table."""

    field: str  # Key of the value in each row.
    header: str
    kind: str = COLUMN_TEXT
    width: int = 150  # In pixels. With fill, the minimum width.
    fill: bool = False  # Takes the width left.
    pinned: bool = False  # Stays on the left when the table scrolls.


class Table(NamedTuple):
    """The table of the recap. Without rows, the empty message replaces it."""

    title: str
    columns: list[Column]
    statuses: list[Status]  # In the order the table sorts them: failures first.
    rows: list[dict[str, Any]]  # One dict per row, with a value for each column field.
    empty_message: str
    search_placeholder: str
    csv_file_name: str


class RecapPage(NamedTuple):
    """Everything a macro shows in its HTML recap."""

    banners: list[Banner]
    metrics: list[Metric]
    sections: list[Section]
    table: Table
    summary: dict[str, Any]  # The recap as JSON data, for the hidden block read by the API.
