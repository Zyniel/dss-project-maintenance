"""Clear Datasets by Tags on a real DSS, as a DSS administrator. Rows 10 and 11 of docs/verification.md."""

from typing import Any

from integration.dss import (
    CLEAR,
    ROW_COUNT,
    add_built_dataset,
    add_uploaded_dataset,
    count_rows,
    row_of,
    run_macro,
)


def test_a_simulation_clears_nothing(scratch_project: Any, connection: str) -> None:
    add_built_dataset(scratch_project, "sales", ["tmp"], connection)

    recap = run_macro(scratch_project, CLEAR, {"included_tags": ["tmp"]})

    assert recap["simulate"] is True
    assert row_of(recap, "sales")["status"] == "WOULD_BE_CLEARED"
    assert count_rows(scratch_project, "sales") == ROW_COUNT


def test_a_real_run_clears_only_the_selected_datasets(scratch_project: Any, connection: str) -> None:
    add_built_dataset(scratch_project, "sales", ["tmp"], connection)
    add_built_dataset(scratch_project, "gold", ["keep"], connection)

    recap = run_macro(scratch_project, CLEAR, {"included_tags": ["tmp"], "simulate": False})

    assert recap["outcome"] == "SUCCESS"
    # The source datasets of the recipes have no tag: only "sales" is selected.
    assert [row["name"] for row in recap["datasets"]] == ["sales"]
    assert row_of(recap, "sales")["status"] == "CLEARED"
    assert count_rows(scratch_project, "sales") == 0
    assert count_rows(scratch_project, "gold") == ROW_COUNT


def test_an_uploaded_dataset_is_never_cleared(scratch_project: Any) -> None:
    add_uploaded_dataset(scratch_project, "upload", ["tmp"])

    config = {"included_tags": ["tmp"], "simulate": False, "purge_without_recipe": True}
    recap = run_macro(scratch_project, CLEAR, config)

    # DSS lists an uploaded dataset as not managed: the macro takes it as external.
    row = row_of(recap, "upload")
    assert (row["status"], row["skip_code"]) == ("SKIPPED", "EXTERNAL")
    assert count_rows(scratch_project, "upload") == ROW_COUNT
