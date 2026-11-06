"""Tests of the report: which tags are used, unknown or unused, and which datasets have no tag."""

from typing import Any

import pytest

from dss_project_maintenance.macros.report_dataset_tags import MACRO
from dss_project_maintenance.macros.report_dataset_tags.report import (
    OPTION_DEFAULTS,
    STATUS_UNKNOWN,
    STATUS_UNUSED,
    STATUS_USED,
    check_category_tag,
    read_options,
)
from support.fakes import PROJECT_KEY, FakeProject, make_dataset
from support.runs import run

CATEGORIES = {"Stage": ["Raw", "Clean"], "Owner": ["Ops"]}


def tag_rows(recap: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["tag"]: row for row in recap["tags"]}


def test_each_tag_lists_the_datasets_carrying_it() -> None:
    project = FakeProject(
        [make_dataset("b", ["tmp", "Stage:Raw"]), make_dataset("a", ["tmp"]), make_dataset("c", [])],
        tag_categories=CATEGORIES,
    )

    recap, progress = run(MACRO, project, {})

    rows = tag_rows(recap)
    assert [row["tag"] for row in recap["tags"]] == ["Stage:Raw", "tmp"]
    assert (rows["tmp"]["status"], rows["tmp"]["datasets"], rows["tmp"]["category"]) == (STATUS_USED, ["a", "b"], "")
    assert (rows["Stage:Raw"]["category"], rows["Stage:Raw"]["datasets"]) == ("Stage", ["b"])
    assert recap["untagged_datasets"] == ["c"]
    assert recap["scanned_count"] == 3
    assert progress == [100]


def test_a_tag_twice_on_a_dataset_counts_once() -> None:
    recap, _ = run(MACRO, FakeProject([make_dataset("a", ["tmp", "tmp"])]), {})

    assert tag_rows(recap)["tmp"]["datasets"] == ["a"]


def test_datasets_shared_by_other_projects_are_left_out() -> None:
    project = FakeProject([make_dataset("local", ["a"]), make_dataset("foreign", ["b"], project_key="OTHER")])

    recap, _ = run(MACRO, project, {"show_unused_tags": False})

    assert [row["tag"] for row in recap["tags"]] == ["a"]
    assert recap["scanned_count"] == 1


# Unknown category tags


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("Stage:Raw", ""),
        ("tmp", ""),
        ("Stage:Rwa", "Category Stage has no tag Rwa"),
        ("Stgae:Raw", "No tag category Stgae"),
    ],
)
def test_check_category_tag(tag: str, expected: str) -> None:
    assert check_category_tag(tag, {"Stage": {"Raw", "Clean"}}) == expected


def test_a_category_tag_the_categories_do_not_know_is_unknown() -> None:
    project = FakeProject([make_dataset("a", ["Stage:Rwa", "Stgae:Raw", "Stage:Clean"])], tag_categories=CATEGORIES)

    recap, _ = run(MACRO, project, {})

    rows = tag_rows(recap)
    assert (rows["Stage:Rwa"]["status"], rows["Stage:Rwa"]["detail"]) == (
        STATUS_UNKNOWN,
        "Category Stage has no tag Rwa",
    )
    assert (rows["Stgae:Raw"]["status"], rows["Stgae:Raw"]["detail"]) == (STATUS_UNKNOWN, "No tag category Stgae")
    assert rows["Stage:Clean"]["status"] == STATUS_USED
    assert recap["categories_checked"] is True
    assert recap["known_categories"] == ["Owner", "Stage"]
    assert recap["notices"] == []


def test_without_admin_rights_the_categories_are_not_checked_and_the_report_says_so() -> None:
    project = FakeProject([make_dataset("a", ["Stage:Rwa"])], tag_categories=CATEGORIES, is_instance_admin=False)

    recap, _ = run(MACRO, project, {})

    assert tag_rows(recap)["Stage:Rwa"]["status"] == STATUS_USED
    assert recap["categories_checked"] is False
    assert recap["known_categories"] is None
    assert [str(notice) for notice in recap["notices"]] == [
        "Category tags not checked. Only DSS administrators can read the categories. "
        "DSS said: Action forbidden, you are not admin."
    ]


# Unused tags


def test_a_tag_of_the_project_list_on_no_dataset_is_unused() -> None:
    project = FakeProject([make_dataset("a", ["tmp"])], project_tags=["tmp", "old", "Stage:Gold"])

    recap, _ = run(MACRO, project, {})

    rows = tag_rows(recap)
    assert [row["tag"] for row in recap["tags"]] == ["old", "Stage:Gold", "tmp"]
    assert (rows["old"]["status"], rows["old"]["datasets"]) == (STATUS_UNUSED, [])
    assert rows["old"]["detail"] == "In the project tag list, on no dataset"
    assert rows["Stage:Gold"]["status"] == STATUS_UNUSED  # Unused, even if its category is unknown.


def test_unused_tags_can_be_left_out() -> None:
    project = FakeProject([make_dataset("a", ["tmp"])], project_tags=["tmp", "old"], tags_error=RuntimeError("no"))

    recap, _ = run(MACRO, project, {"show_unused_tags": False})

    assert [row["tag"] for row in recap["tags"]] == ["tmp"]
    assert recap["notices"] == []  # The project tag list is not even read.


def test_an_unreadable_project_tag_list_is_a_notice() -> None:
    project = FakeProject([make_dataset("a", ["tmp"])], tags_error=RuntimeError("timeout"))

    recap, _ = run(MACRO, project, {})

    assert [row["tag"] for row in recap["tags"]] == ["tmp"]
    assert [str(notice) for notice in recap["notices"]] == [
        "Unused tags not listed. The project tag list could not be read. DSS said: timeout."
    ]


# Options


def test_options_show_unused_tags_and_aggregate_by_tag_by_default() -> None:
    options = read_options({}, PROJECT_KEY)

    assert options["show_unused_tags"] is OPTION_DEFAULTS["show_unused_tags"] is True
    assert options["aggregate_by_tag"] is OPTION_DEFAULTS["aggregate_by_tag"] is True
    assert options["recap_dataset"] is None


@pytest.mark.parametrize("option", ["show_unused_tags", "aggregate_by_tag"])
@pytest.mark.parametrize("value", [None, "false", 0])
def test_only_a_real_false_unchecks_an_option(option: str, value: Any) -> None:
    assert read_options({option: value}, PROJECT_KEY)[option] is True


def test_not_aggregated_reports_the_same_tags() -> None:
    project = FakeProject([make_dataset("a", ["tmp"]), make_dataset("b", [])])

    aggregated, _ = run(MACRO, project, {})
    not_aggregated, _ = run(MACRO, project, {"aggregate_by_tag": False})

    assert not_aggregated["options"]["aggregate_by_tag"] is False
    assert not_aggregated["tags"] == aggregated["tags"]  # Only the table of the recap changes.
