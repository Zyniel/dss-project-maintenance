"""Tests of writing the summary dataset: its schema, the append mode, and never replacing other data."""

import pytest

from dss_maintenance.recap.dataset import format_flag, write_recap_dataset
from support.fakes import FakeRecapDataset

COLUMNS = ["run_id", "dataset", "status"]
NEW_ROW = ["1", "ds", "DONE"]
EARLIER_ROW = ["0", "ds", "DONE"]


def test_format_flag() -> None:
    assert (format_flag(True), format_flag(False), format_flag(None)) == ("true", "false", "")


def test_a_new_empty_dataset_gets_the_schema_and_the_rows() -> None:
    dataset = FakeRecapDataset()

    written = write_recap_dataset(dataset, COLUMNS, [NEW_ROW], keep_earlier_runs=True)

    assert written == 1
    assert dataset.schema == [{"name": column, "type": "string"} for column in COLUMNS]
    assert dataset.rows == [NEW_ROW]


def test_append_mode_adds_the_rows_with_the_append_mode_of_dss() -> None:
    dataset = FakeRecapDataset(COLUMNS, [EARLIER_ROW])

    write_recap_dataset(dataset, COLUMNS, [NEW_ROW], keep_earlier_runs=True)

    # The earlier rows are never read (the fake fails if they are): DSS appends the new ones.
    assert dataset.spec_item["appendMode"] is True
    assert dataset.rows == [EARLIER_ROW, NEW_ROW]


def test_each_run_replaces_the_recap_when_append_mode_is_unchecked() -> None:
    dataset = FakeRecapDataset(COLUMNS, [EARLIER_ROW])

    write_recap_dataset(dataset, COLUMNS, [NEW_ROW], keep_earlier_runs=False)

    assert dataset.spec_item["appendMode"] is False
    assert dataset.rows == [NEW_ROW]


@pytest.mark.parametrize("keep_earlier_runs", [True, False])
def test_a_dataset_holding_other_columns_is_never_written(keep_earlier_runs: bool) -> None:
    dataset = FakeRecapDataset(["customer_id", "amount"], [["c1", "10"]])

    with pytest.raises(ValueError, match=r"other columns \(customer_id, amount\)"):
        write_recap_dataset(dataset, COLUMNS, [NEW_ROW], keep_earlier_runs)

    assert dataset.rows == [["c1", "10"]]


def test_a_run_without_rows_leaves_the_history_as_it_is() -> None:
    dataset = FakeRecapDataset(COLUMNS, [EARLIER_ROW])

    assert write_recap_dataset(dataset, COLUMNS, [], keep_earlier_runs=True) == 0
    assert dataset.rows == [EARLIER_ROW]
