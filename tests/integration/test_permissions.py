"""Who sees and runs each macro, with users who are not DSS administrators. Rows 8, 13, 22 and 24 of
docs/verification.md.

These tests need the API keys of an editor and a reader in the config file. Without them, they are skipped.
"""

from typing import Any

import pytest

from integration.dss import (
    CLEAR,
    REPORT,
    ROW_COUNT,
    add_built_dataset,
    count_rows,
    dss_error,
    give_access,
    list_macro_ids,
    row_of,
    run_macro,
)


def test_an_editor_sees_both_macros(scratch_project: Any, editor: Any) -> None:
    project = give_access(scratch_project, editor, write=True)

    assert {CLEAR, REPORT} <= list_macro_ids(project)


def test_an_editor_clears_without_reading_the_sharing(scratch_project: Any, editor: Any, connection: str) -> None:
    add_built_dataset(scratch_project, "sales", ["tmp"], connection)
    project = give_access(scratch_project, editor, write=True)

    recap = run_macro(project, CLEAR, {"included_tags": ["tmp"], "simulate": False})

    # Only project administrators can read the sharing: the run goes on, with a notice.
    assert recap["sharing_checked"] is False
    assert [notice for notice in recap["notices"] if notice.startswith("Sharing not checked.")]
    assert row_of(recap, "sales")["status"] == "CLEARED"
    assert count_rows(scratch_project, "sales") == 0


def test_an_editor_cannot_skip_shared_datasets(scratch_project: Any, editor: Any, connection: str) -> None:
    add_built_dataset(scratch_project, "sales", ["tmp"], connection)
    project = give_access(scratch_project, editor, write=True)

    with pytest.raises(dss_error(), match="Sharing not checked"):
        run_macro(project, CLEAR, {"included_tags": ["tmp"], "simulate": False, "purge_shared": False})

    assert count_rows(scratch_project, "sales") == ROW_COUNT


def test_a_reader_sees_only_the_report(scratch_project: Any, reader: Any) -> None:
    project = give_access(scratch_project, reader, write=False)

    macro_ids = list_macro_ids(project)

    assert REPORT in macro_ids
    assert CLEAR not in macro_ids


def test_a_reader_cannot_clear_data(scratch_project: Any, reader: Any, connection: str) -> None:
    add_built_dataset(scratch_project, "sales", ["tmp"], connection)
    project = give_access(scratch_project, reader, write=False)

    with pytest.raises(dss_error()):
        run_macro(project, CLEAR, {"included_tags": ["tmp"], "simulate": False})

    assert count_rows(scratch_project, "sales") == ROW_COUNT


def test_a_reader_runs_the_report_without_the_global_categories(
    scratch_project: Any, reader: Any, connection: str
) -> None:
    add_built_dataset(scratch_project, "sales", ["Stage:Raw"], connection)
    project = give_access(scratch_project, reader, write=False)

    recap = run_macro(project, REPORT, {})

    # Only DSS administrators can read the tag categories of the instance.
    assert recap["categories_checked"] is False
    assert [row["tag"] for row in recap["tags"] if row["tag"] == "Stage:Raw"]
