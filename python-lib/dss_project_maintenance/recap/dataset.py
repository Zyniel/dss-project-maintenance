"""Write the recap of a run to a dataset of the project: one row per item and per run."""

from typing import Any, Optional


def format_flag(value: Optional[bool]) -> str:
    """Return "true", "false", or "" when the macro could not check."""
    if value is None:
        return ""
    return "true" if value else "false"


def write_recap_dataset(dataset: Any, columns: list[str], rows: list[list[str]], keep_earlier_runs: bool) -> int:
    """Write the recap rows to the recap dataset and return how many were written.

    Every column is stored as text. DSS still detects booleans and numbers when the dataset is
    explored.

    With keep_earlier_runs ("Append mode"), DSS adds the rows to the data: the write session uses
    the append mode of DSS, so the earlier runs are never read nor written again, and two runs that
    write at the same time both keep their rows. Otherwise the rows replace the data.

    :param dataset: a dataiku.Dataset, or any object with the same methods
    :param columns: the columns of the recap dataset of the macro
    :raises ValueError: if the dataset already holds other columns, so that its data is never replaced
    """
    current_columns = [column["name"] for column in dataset.read_schema(raise_if_empty=False)]
    if current_columns and current_columns != columns:
        shown = ", ".join(current_columns[:5]) + (", ..." if len(current_columns) > 5 else "")
        raise ValueError(
            f"it already holds other columns ({shown}). Pick a new empty dataset, or one an earlier run wrote to."
        )

    if keep_earlier_runs and not rows:
        return 0  # Nothing to add: leave the dataset as it is.

    if not current_columns:
        dataset.write_schema([{"name": column, "type": "string"} for column in columns])
    # Outside a recipe, dataiku.Dataset writes with "appendMode" false: the data is replaced.
    dataset.spec_item["appendMode"] = keep_earlier_runs
    with dataset.get_writer() as writer:
        for values in rows:
            writer.write_tuple(values)
    return len(rows)
