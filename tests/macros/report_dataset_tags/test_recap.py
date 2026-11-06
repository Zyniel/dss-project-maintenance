"""Tests of the recap: the JSON summary, the recap dataset rows and the HTML page."""

import json
from typing import Any, Optional

from dss_project_maintenance.macros.report_dataset_tags import MACRO
from dss_project_maintenance.macros.report_dataset_tags.recap import (
    COLUMNS_BY_TAG,
    COLUMNS_BY_TAG_AND_DATASET,
    NO_TAG,
    RECAP_COLUMNS,
    build_recap_page,
    build_recap_rows,
    build_summary,
    describe_counts,
    describe_failures,
)
from dss_project_maintenance.recap.html import build_recap_html
from dss_project_maintenance.recap.page import COLUMN_TAGS
from support.fakes import FakeProject, make_dataset
from support.runs import run

CATEGORIES = {"Stage": ["Raw", "Clean"]}


def sample_recap(config: Optional[dict[str, Any]] = None, **project_values: Any) -> dict[str, Any]:
    project = FakeProject(
        [
            make_dataset("a", ["tmp", "Stage:Raw"]),
            make_dataset("b", ["Stage:Rwa"]),
            make_dataset("c", []),
            make_dataset("d", []),
        ],
        project_tags=["tmp", "Stage:Raw", "Stage:Rwa", "old"],
        tag_categories=CATEGORIES,
        **project_values,
    )
    recap, _ = run(MACRO, project, config or {})
    return recap


def metric(html: str, label: str) -> str:
    """Return the value displayed above a metric label."""
    before_label = html[: html.index(f'<span class="dtp-metric-label">{label}<')]
    value_start = before_label.rindex('">') + 2
    return before_label[value_start:].replace("</span>", "")


def test_summary_is_plain_json_with_the_counts() -> None:
    summary = json.loads(json.dumps(build_summary(sample_recap())))

    assert summary["counts"] == {
        "datasets": 4,
        "tagged": 2,
        "untagged": 2,
        "tags": 4,
        "used": 2,
        "unknown": 1,
        "unused": 1,
    }
    assert summary["macro"] == "report-dataset-tags"
    assert summary["untagged_datasets"] == ["c", "d"]
    assert summary["tags"][0] == {
        "tag": "old",
        "category": "",
        "status": "UNUSED",
        "detail": "In the project tag list, on no dataset",
        "dataset_count": 0,
        "datasets": [],
    }


def test_describe_counts_for_the_log() -> None:
    assert describe_counts(sample_recap()) == "4 datasets, 2 with no tag; 4 tags: 2 used, 1 unknown, 1 unused"


def test_recap_rows_hold_one_row_per_tag_and_dataset() -> None:
    recap = sample_recap()

    records = [dict(zip(RECAP_COLUMNS, row)) for row in build_recap_rows(recap)]

    assert MACRO.recap_columns == RECAP_COLUMNS
    assert [(r["tag"], r["tag_category"], r["tag_status"], r["dataset"]) for r in records] == [
        ("old", "", "UNUSED", ""),
        ("Stage:Raw", "Stage", "USED", "a"),
        ("Stage:Rwa", "Stage", "UNKNOWN", "b"),
        ("tmp", "", "USED", "a"),
        ("", "", "UNTAGGED", "c"),
        ("", "", "UNTAGGED", "d"),
    ]
    assert records[1]["dataset_type"] == "PostgreSQL"
    assert records[0]["dataset_type"] == ""
    assert {record["run_id"] for record in records} == {recap["run_id"]}


def test_nothing_in_the_work_of_a_report_can_fail() -> None:
    assert describe_failures(sample_recap()) == ""


def test_the_table_has_a_row_per_tag_and_one_for_the_datasets_with_no_tag() -> None:
    table = build_recap_page(sample_recap()).table

    assert [row["tag"] for row in table.rows] == ["old", "Stage:Raw", "Stage:Rwa", "tmp", ""]
    assert NO_TAG == ""  # No real tag can be taken for this row.
    assert table.rows[-1] == {
        "tag": NO_TAG,
        "status": "UNTAGGED",
        "detail": "Datasets with no tag",
        "dataset_count": 2,
        "datasets": "c, d",  # Plain text, not chips.
        "category": "",
    }
    assert table.columns == COLUMNS_BY_TAG
    assert all(set(row) == {column.field for column in COLUMNS_BY_TAG} for row in table.rows)
    assert [status.code for status in table.statuses] == ["UNKNOWN", "UNTAGGED", "UNUSED", "USED"]


def test_not_aggregated_the_table_has_a_row_per_tag_and_dataset() -> None:
    table = build_recap_page(sample_recap({"aggregate_by_tag": False})).table

    assert table.title == "Tags and datasets"
    assert table.columns == COLUMNS_BY_TAG_AND_DATASET
    assert [(row["tag"], row["dataset"], row["status"]) for row in table.rows] == [
        ("old", "", "UNUSED"),
        ("Stage:Raw", "a", "USED"),
        ("Stage:Rwa", "b", "UNKNOWN"),
        ("tmp", "a", "USED"),
        (NO_TAG, "c", "UNTAGGED"),
        (NO_TAG, "d", "UNTAGGED"),
    ]
    assert table.rows[1] == {
        "tag": "Stage:Raw",
        "status": "USED",
        "dataset": "a",
        "type": "PostgreSQL",
        "category": "Stage",
        "detail": "",
    }
    assert table.rows[-1]["detail"] == "No tag"
    assert all(set(row) == {column.field for column in COLUMNS_BY_TAG_AND_DATASET} for row in table.rows)


def test_dataset_names_are_never_shown_as_chips() -> None:
    for columns in [COLUMNS_BY_TAG, COLUMNS_BY_TAG_AND_DATASET]:
        assert COLUMN_TAGS not in [column.kind for column in columns]


def test_the_html_recap_gives_the_figures_categories_and_options() -> None:
    recap = sample_recap()

    html = build_recap_html(recap, build_recap_page(recap))

    assert "Report Dataset Tags · Project TEST · Run by jdoe" in html
    assert (metric(html, "Datasets"), metric(html, "Tagged"), metric(html, "Untagged")) == ("4", "2", "2")
    assert [metric(html, label) for label in ["Tags", "Used", "Unknown", "Unused"]] == ["4", "2", "1", "1"]
    assert '<div class="dtp-metric" data-status="UNTAGGED">' in html
    assert '<span class="dtp-tag">Stage: 2 tags, 2 datasets</span>' in html
    assert '<span class="dtp-tag">Show unused tags: yes</span>' in html
    assert '<span class="dtp-tag">Aggregate by tag: yes</span>' in html
    table = html[html.index("<table>") : html.index("</table>")]
    assert '<td class="dtp-wrap">c, d</td>' in table  # Dataset names as plain text.
    assert "dtp-tag" not in table
    assert "Simulation" not in html


def test_an_unknown_category_stands_out_and_unchecked_figures_are_hidden() -> None:
    project = FakeProject([make_dataset("a", ["Stgae:Raw"])], tag_categories=CATEGORIES)
    recap, _ = run(MACRO, project, {"show_unused_tags": False})

    html = build_recap_html(recap, build_recap_page(recap))

    assert '<span class="dtp-tag dtp-tag-caution">Stgae: 1 tag, 1 dataset</span>' in html
    assert 'dtp-metric-label">Unused' not in html

    recap, _ = run(MACRO, FakeProject([make_dataset("a", ["x"])], is_instance_admin=False), {})
    html = build_recap_html(recap, build_recap_page(recap))
    assert 'dtp-metric-label">Unknown' not in html
    assert "No category tag on the datasets." in html
    assert '<div class="dtp-banner"><strong>Category tags not checked.</strong> ' in html


def test_a_project_with_no_dataset_and_no_tag_shows_a_message() -> None:
    recap, _ = run(MACRO, FakeProject([]), {})

    html = build_recap_html(recap, build_recap_page(recap))

    assert "<p>This project has no dataset and no tag.</p>" in html
