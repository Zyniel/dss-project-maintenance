"""Clear Datasets by Tags on a real DSS, as a DSS administrator. Rows 10, 11 and 28 of docs/verification.md."""

from typing import Any

import pytest

from integration.dss import (
    CLEAR,
    ROW_COUNT,
    add_built_dataset,
    add_uploaded_dataset,
    count_rows,
    dss_error,
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


def test_all_datasets_without_excluded_tags_clears_every_managed_dataset(scratch_project: Any, connection: str) -> None:
    add_built_dataset(scratch_project, "sales", [], connection)

    recap = run_macro(scratch_project, CLEAR, {"included_scope": "ALL_DATASETS", "simulate": False})

    assert (recap["outcome"], recap["included_scope"]) == ("SUCCESS", "ALL_DATASETS")
    assert row_of(recap, "sales")["status"] == "CLEARED"
    # The uploaded source of the recipe is selected too, and skipped: DSS lists it as not managed.
    source = row_of(recap, "sales_source")
    assert (source["status"], source["skip_code"]) == ("SKIPPED", "EXTERNAL")
    assert count_rows(scratch_project, "sales") == 0
    assert count_rows(scratch_project, "sales_source") == ROW_COUNT


def test_all_datasets_keeps_the_excluded_datasets(scratch_project: Any, connection: str) -> None:
    add_built_dataset(scratch_project, "sales", ["tmp"], connection)
    add_built_dataset(scratch_project, "gold", ["keep"], connection)

    config = {"included_scope": "ALL_DATASETS", "excluded_tags": ["keep"], "simulate": False}
    recap = run_macro(scratch_project, CLEAR, config)

    assert row_of(recap, "sales")["status"] == "CLEARED"
    assert row_of(recap, "gold")["status"] == "EXCLUDED"
    assert count_rows(scratch_project, "sales") == 0
    assert count_rows(scratch_project, "gold") == ROW_COUNT


def test_only_excluded_tags_are_refused(scratch_project: Any, connection: str) -> None:
    add_built_dataset(scratch_project, "sales", [], connection)

    with pytest.raises(dss_error(), match="Give at least one included tag, or choose 'All datasets' in 'Include'"):
        run_macro(scratch_project, CLEAR, {"excluded_tags": ["keep"], "simulate": False})

    assert count_rows(scratch_project, "sales") == ROW_COUNT
