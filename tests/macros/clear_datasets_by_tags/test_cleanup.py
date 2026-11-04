"""Tests of the cleanup: which datasets the macro selects, excludes and skips, and how it clears them."""

import logging
from typing import Any

import pytest

from dss_maintenance.core.macro import RunStopped
from dss_maintenance.macros.clear_datasets_by_tags import MACRO
from dss_maintenance.macros.clear_datasets_by_tags.cleanup import (
    SKIP_EXTERNAL,
    SKIP_PARTITIONED,
    SKIP_RECAP_DATASET,
    SKIP_SHARED,
    SKIP_STOPPED,
    SKIP_WITHOUT_RECIPE,
    STATUS_CLEARED,
    STATUS_EXCLUDED,
    STATUS_FAILED,
    STATUS_SKIPPED,
    STATUS_WOULD_BE_CLEARED,
)
from support.fakes import FakeProject, make_dataset
from support.runs import row_of, run, status_of

REAL_RUN = {"simulate": False}

# Selecting the datasets


def test_included_tags_select_the_datasets_carrying_any_of_them_by_default() -> None:
    project = FakeProject(
        [
            make_dataset("both", ["a", "other", "Stage:Raw"]),
            make_dataset("one", ["Stage:Raw"]),
            make_dataset("none", ["other"]),
        ]
    )
    config = {"included_tags": ["a"], "included_category_tags": ["Stage:Raw"], **REAL_RUN}

    recap, _ = run(MACRO, project, config)

    assert [row["name"] for row in recap["datasets"]] == ["both", "one"]
    assert row_of(recap, "both")["included_tags"] == ["a", "Stage:Raw"]
    assert project.cleared == ["both", "one"]
    assert recap["scanned_count"] == 3


def test_all_included_tags_select_the_datasets_carrying_every_one() -> None:
    project = FakeProject([make_dataset("both", ["a", "Stage:Raw"]), make_dataset("one", ["Stage:Raw"])])
    config = {"included_tags": ["a"], "included_category_tags": ["Stage:Raw"], "included_match": "ALL", **REAL_RUN}

    recap, _ = run(MACRO, project, config)

    assert [row["name"] for row in recap["datasets"]] == ["both"]
    assert project.cleared == ["both"]


@pytest.mark.parametrize("dataset_tag", ["TEMPORARY", "temporary2", "Stage", "Raw", "Stage:raw"])
def test_matching_is_exact_and_case_sensitive(dataset_tag: str) -> None:
    project = FakeProject([make_dataset("ds", [dataset_tag])])
    config = {"included_tags": ["temporary"], "included_category_tags": ["Stage:Raw"]}

    recap, _ = run(MACRO, project, config)

    assert recap["datasets"] == []


def test_excluded_tags_alone_clear_every_other_dataset() -> None:
    project = FakeProject(
        [make_dataset("untagged", []), make_dataset("other", ["x"]), make_dataset("gold", ["Stage:Gold", "x"])]
    )

    recap, _ = run(MACRO, project, {"excluded_category_tags": ["Stage:Gold"], **REAL_RUN})

    assert project.cleared == ["other", "untagged"]
    gold = row_of(recap, "gold")
    assert (gold["status"], gold["detail"]) == (STATUS_EXCLUDED, "Has excluded tags")
    assert gold["excluded_tags"] == ["Stage:Gold"]


def test_an_excluded_dataset_is_never_cleared_even_when_included() -> None:
    project = FakeProject(
        [
            make_dataset("included_only", ["tmp"]),
            make_dataset("included_and_excluded", ["tmp", "keep"]),
            make_dataset("excluded_only", ["keep"]),
            make_dataset("neither", []),
        ]
    )

    recap, _ = run(MACRO, project, {"included_tags": ["tmp"], "excluded_tags": ["keep"], **REAL_RUN})

    assert project.cleared == ["included_only"]
    assert status_of(recap, "included_and_excluded") == STATUS_EXCLUDED
    assert [row["name"] for row in recap["datasets"]] == ["included_and_excluded", "included_only"]


def test_all_excluded_tags_exclude_only_the_datasets_carrying_every_one() -> None:
    project = FakeProject(
        [make_dataset("both", ["tmp", "k1", "k2"]), make_dataset("one", ["tmp", "k1"]), make_dataset("k2", ["k2"])]
    )
    config = {"included_tags": ["tmp"], "excluded_tags": ["k1", "k2"], "excluded_match": "ALL", **REAL_RUN}

    recap, _ = run(MACRO, project, config)

    assert project.cleared == ["one"]
    assert status_of(recap, "both") == STATUS_EXCLUDED
    assert row_of(recap, "one")["excluded_tags"] == ["k1"]


def test_a_tag_in_both_lists_is_excluded_and_reported() -> None:
    project = FakeProject([make_dataset("input", ["CDP-DatasetType:Input"]), make_dataset("other", ["tmp"])])
    config = {
        "included_category_tags": ["CDP-DatasetType:Input"],
        "excluded_category_tags": ["CDP-DatasetType:Input"],
        **REAL_RUN,
    }

    recap, _ = run(MACRO, project, config)

    assert project.cleared == []
    assert status_of(recap, "input") == STATUS_EXCLUDED
    assert recap["notices"] == [
        "Tags both included and excluded: CDP-DatasetType:Input. The excluded tags still apply: check the two lists."
    ]


# Datasets that are never cleared


def test_datasets_shared_by_other_projects_are_never_handled() -> None:
    project = FakeProject(
        [make_dataset("foreign", ["a"], project_key="OTHER"), make_dataset("local", ["a"]), make_dataset("kept", ["k"])]
    )

    recap, _ = run(MACRO, project, {"included_tags": ["a"], "excluded_tags": ["k"], **REAL_RUN})

    assert project.cleared == ["local"]
    assert "foreign" not in [row["name"] for row in recap["datasets"]]
    assert recap["scanned_count"] == 2


def test_external_datasets_are_never_cleared_and_the_reason_names_the_connection() -> None:
    project = FakeProject([make_dataset("external", ["a"], managed=False)])

    recap, _ = run(MACRO, project, {"included_tags": ["a"], **REAL_RUN})

    assert project.cleared == []
    row = row_of(recap, "external")
    assert (row["status"], row["skip_code"]) == (STATUS_SKIPPED, SKIP_EXTERNAL)
    assert row["detail"] == "Is external (connection pg_prod)"


def test_a_dataset_without_the_managed_flag_counts_as_external() -> None:
    dataset = make_dataset("unknown", ["a"])
    del dataset["managed"]
    del dataset["params"]["connection"]
    project = FakeProject([dataset])

    recap, _ = run(MACRO, project, {"included_tags": ["a"], **REAL_RUN})

    assert project.cleared == []
    assert row_of(recap, "unknown")["detail"] == "Is external"  # No connection to name.


def test_the_recap_dataset_is_never_cleared_by_its_own_run() -> None:
    project = FakeProject([make_dataset("recap", []), make_dataset("data", []), make_dataset("kept", ["k"])])

    recap, _ = run(MACRO, project, {"excluded_tags": ["k"], "recap_dataset": "recap", **REAL_RUN})

    assert project.cleared == ["data"]
    assert (row_of(recap, "recap")["skip_code"], row_of(recap, "recap")["detail"]) == (
        SKIP_RECAP_DATASET,
        "Is the summary dataset",
    )


# Datasets shared with other projects


def test_shared_datasets_are_skipped_when_the_option_is_unchecked() -> None:
    project = FakeProject([make_dataset("shared", ["a"]), make_dataset("local", ["a"])], shared={"shared": ["PROJ_B"]})
    config = {"included_tags": ["a"], "purge_shared": False, **REAL_RUN}

    recap, _ = run(MACRO, project, config)

    assert project.cleared == ["local"]
    row = row_of(recap, "shared")
    assert (row["status"], row["skip_code"]) == (STATUS_SKIPPED, SKIP_SHARED)
    assert row["detail"] == "Is shared with PROJ_B; 'Clear shared datasets' is unchecked"
    assert recap["sharing_checked"] is True


@pytest.mark.parametrize("purge_shared", [None, True, "false", 0])
def test_shared_datasets_are_cleared_by_default_with_a_warning_naming_the_projects(purge_shared: Any) -> None:
    project = FakeProject([make_dataset("shared", ["a"])], shared={"shared": ["PROJ_C", "PROJ_B"]})
    config = {"included_tags": ["a"], **REAL_RUN}
    if purge_shared is not None:
        config["purge_shared"] = purge_shared

    recap, _ = run(MACRO, project, config)

    assert project.cleared == ["shared"]
    row = row_of(recap, "shared")
    assert (row["is_shared"], row["shared_with"]) == (True, ["PROJ_B", "PROJ_C"])
    assert row["warnings"] == ["Shared with PROJ_B, PROJ_C: the projects using it can break"]


def test_sharing_is_shown_in_a_simulation() -> None:
    project = FakeProject([make_dataset("shared", ["a"])], shared={"shared": ["PROJ_B"]})

    recap, _ = run(MACRO, project, {"included_tags": ["a"], "purge_shared": True})

    assert status_of(recap, "shared") == STATUS_WOULD_BE_CLEARED
    assert row_of(recap, "shared")["warnings"] == ["Shared with PROJ_B: the projects using it can break"]


def test_a_real_run_of_an_editor_that_skips_shared_datasets_stops_since_they_cannot_be_found() -> None:
    project = FakeProject([make_dataset("ds", ["a"])], is_admin=False)

    with pytest.raises(RunStopped, match="Nothing was cleared. Shared datasets cannot be skipped"):
        run(MACRO, project, {"included_tags": ["a"], "purge_shared": False, **REAL_RUN})

    assert project.cleared == []


def test_editors_who_check_the_option_clear_and_are_told_sharing_was_not_checked() -> None:
    project = FakeProject([make_dataset("shared", ["a"])], shared={"shared": ["PROJ_B"]}, is_admin=False)

    recap, _ = run(MACRO, project, {"included_tags": ["a"], "purge_shared": True, **REAL_RUN})

    assert project.cleared == ["shared"]
    assert recap["sharing_checked"] is False
    assert row_of(recap, "shared")["is_shared"] is None
    assert row_of(recap, "shared")["warnings"] == ["Sharing not checked: other projects may use it"]
    assert len(recap["notices"]) == 1
    assert recap["notices"][0].startswith("Sharing not checked.")
    assert "not admin" in recap["notices"][0]


def test_a_simulation_shows_why_a_real_run_would_stop() -> None:
    project = FakeProject([make_dataset("ds", ["a"])], is_admin=False)

    recap, _ = run(MACRO, project, {"included_tags": ["a"], "purge_shared": False})

    assert recap["blockers"][0].startswith("Shared datasets cannot be skipped.")
    assert status_of(recap, "ds") == STATUS_WOULD_BE_CLEARED


# Partitioned datasets


@pytest.mark.parametrize("purge_partitioned", [None, False, "true"])
def test_partitioned_datasets_are_skipped_unless_the_option_is_true(purge_partitioned: Any) -> None:
    project = FakeProject([make_dataset("partitioned", ["a"], partitioned=True)])
    config = {"included_tags": ["a"], **REAL_RUN}
    if purge_partitioned is not None:
        config["purge_partitioned"] = purge_partitioned

    recap, _ = run(MACRO, project, config)

    assert project.cleared == []
    row = row_of(recap, "partitioned")
    assert row["skip_code"] == SKIP_PARTITIONED
    assert row["detail"] == "Is partitioned by day, country; 'Clear partitioned datasets' is unchecked"


def test_checked_partitioned_datasets_are_cleared_with_a_warning() -> None:
    project = FakeProject([make_dataset("partitioned", ["a"], partitioned=True)])

    recap, _ = run(MACRO, project, {"included_tags": ["a"], "purge_partitioned": True, **REAL_RUN})

    assert project.cleared == ["partitioned"]
    assert row_of(recap, "partitioned")["warnings"] == ["All partitions are cleared (partitioned by day, country)"]


# Datasets no recipe builds


def test_datasets_no_recipe_builds_are_skipped_by_default() -> None:
    project = FakeProject([make_dataset("source", ["a"]), make_dataset("built", ["a"])], without_recipe=["source"])

    recap, _ = run(MACRO, project, {"included_tags": ["a"], **REAL_RUN})

    assert project.cleared == ["built"]
    row = row_of(recap, "source")
    assert row["skip_code"] == SKIP_WITHOUT_RECIPE
    assert row["detail"] == "Has no recipe; 'Clear datasets with no recipe' is unchecked"
    assert row_of(recap, "built")["built_by_recipe"] is True


def test_checked_datasets_no_recipe_builds_are_cleared_with_a_warning() -> None:
    project = FakeProject([make_dataset("source", ["a"]), make_dataset("built", ["a"])], without_recipe=["source"])

    recap, _ = run(MACRO, project, {"included_tags": ["a"], "purge_without_recipe": True, **REAL_RUN})

    assert project.cleared == ["built", "source"]
    assert row_of(recap, "source")["warnings"] == ["No recipe builds it: its data cannot be rebuilt"]
    assert row_of(recap, "source")["built_by_recipe"] is False


def test_an_unreadable_flow_stops_a_real_run_by_default() -> None:
    project = FakeProject([make_dataset("ds", ["a"])], flow_error=RuntimeError("timeout"))

    with pytest.raises(RunStopped, match="Datasets no recipe builds cannot be skipped"):
        run(MACRO, project, {"included_tags": ["a"], **REAL_RUN})

    assert project.cleared == []


def test_an_unreadable_flow_is_a_notice_when_the_option_is_checked() -> None:
    project = FakeProject([make_dataset("ds", ["a"])], flow_error=RuntimeError("timeout"))

    recap, _ = run(MACRO, project, {"included_tags": ["a"], "purge_without_recipe": True, **REAL_RUN})

    assert project.cleared == ["ds"]
    assert recap["recipes_checked"] is False
    assert recap["notices"] == [
        "Recipes not checked. Reading the Flow failed (timeout). Datasets no recipe builds are cleared like the others."
    ]


# Excluded tags


def test_an_excluded_tag_on_no_dataset_neither_stops_nor_warns() -> None:
    project = FakeProject([make_dataset("gold", ["Stage:Gold"]), make_dataset("other", [])])

    recap, _ = run(MACRO, project, {"excluded_tags": ["NoInList", "Stage:Gold"], **REAL_RUN})

    assert project.cleared == ["other"]
    assert recap["excluded_tag_counts"] == {"NoInList": 0, "Stage:Gold": 1}
    assert (recap["blockers"], recap["notices"]) == ([], [])


def test_an_excluded_tag_counts_every_dataset_carrying_it_not_only_the_selected_ones() -> None:
    project = FakeProject([make_dataset("tmp", ["tmp"]), make_dataset("keep_only", ["keep"])])

    recap, _ = run(MACRO, project, {"included_tags": ["tmp"], "excluded_tags": ["keep"], **REAL_RUN})

    assert recap["blockers"] == []
    assert project.cleared == ["tmp"]


# Simulation


@pytest.mark.parametrize("simulate", [True, None, "false", 0])
def test_only_an_explicit_false_clears_data(simulate: Any) -> None:
    project = FakeProject([make_dataset("ds", ["a"])])

    recap, _ = run(MACRO, project, {"included_tags": ["a"], "simulate": simulate})

    assert project.cleared == []
    assert status_of(recap, "ds") == STATUS_WOULD_BE_CLEARED
    assert row_of(recap, "ds")["duration"] is None


def test_simulation_is_the_default_and_still_reports_skipped_datasets() -> None:
    project = FakeProject([make_dataset("ds", ["a"]), make_dataset("external", ["a"], managed=False)])

    recap, _ = run(MACRO, project, {"included_tags": ["a"]})

    assert project.cleared == []
    assert recap["simulate"] is True
    assert status_of(recap, "ds") == STATUS_WOULD_BE_CLEARED
    assert status_of(recap, "external") == STATUS_SKIPPED


@pytest.mark.parametrize(("simulate", "final_status"), [(True, STATUS_WOULD_BE_CLEARED), (False, STATUS_CLEARED)])
def test_the_log_gives_each_decision_in_the_same_words_in_both_modes(
    caplog: pytest.LogCaptureFixture, simulate: bool, final_status: str
) -> None:
    caplog.set_level(logging.INFO)
    project = FakeProject([make_dataset("ds", ["a"]), make_dataset("external", ["a"], managed=False)])

    recap, _ = run(MACRO, project, {"included_tags": ["a"], "simulate": simulate})

    # The decisions come before any clear: a real run never logs "Cleared (Simulate)".
    decisions = [message for message in caplog.messages if message.startswith("Decision for ")]
    assert decisions == [
        "Decision for ds: To clear - Has included tags",
        "Decision for external: Skipped - Is external (connection pg_prod)",
    ]
    assert status_of(recap, "ds") == final_status


# Clearing and reporting


def test_a_failure_does_not_stop_the_following_datasets() -> None:
    project = FakeProject(
        [make_dataset(name, ["a"]) for name in ("d1", "d2", "d3", "d4")],
        clear_answers={"d2": RuntimeError("boom")},
    )

    recap, progress = run(MACRO, project, {"included_tags": ["a"], **REAL_RUN})

    assert project.cleared == ["d1", "d2", "d3", "d4"]
    assert status_of(recap, "d2") == STATUS_FAILED
    assert row_of(recap, "d2")["detail"] == "RuntimeError: boom"
    assert status_of(recap, "d3") == STATUS_CLEARED
    assert progress == [25, 50, 75, 100]
    for row in recap["datasets"]:
        assert row["duration"] >= 0


def test_a_failure_reported_in_the_response_counts_as_failed() -> None:
    failed_clear = {
        "fatal": True,
        "error": True,
        "success": False,
        "messages": [{"severity": "ERROR", "details": "Unable to clear data", "message": "Failed to drop data"}],
    }
    project = FakeProject([make_dataset("ds", ["a"])], clear_answers={"ds": failed_clear})

    recap, _ = run(MACRO, project, {"included_tags": ["a"], **REAL_RUN})

    assert status_of(recap, "ds") == STATUS_FAILED
    assert row_of(recap, "ds")["detail"] == "ERROR: Unable to clear data"


@pytest.mark.parametrize("flag", ["error", "fatal"])
def test_either_error_flag_counts_as_failed(flag: str) -> None:
    project = FakeProject([make_dataset("ds", ["a"])], clear_answers={"ds": {flag: True, "messages": []}})

    recap, _ = run(MACRO, project, {"included_tags": ["a"], **REAL_RUN})

    assert status_of(recap, "ds") == STATUS_FAILED
    assert row_of(recap, "ds")["detail"] == "DSS reported an error without any message."


def test_success_false_without_error_is_cleared_and_keeps_the_warnings_of_dss() -> None:
    answer = {"success": False, "messages": [{"severity": "WARNING", "message": "Table was already empty"}]}
    project = FakeProject([make_dataset("ds", ["a"])], clear_answers={"ds": answer})

    recap, _ = run(MACRO, project, {"included_tags": ["a"], **REAL_RUN})

    assert status_of(recap, "ds") == STATUS_CLEARED
    assert row_of(recap, "ds")["detail"] == "WARNING: Table was already empty"


@pytest.mark.parametrize("answer", [None, "done", ["a"], {"messages": ["not a message"]}])
def test_an_unexpected_answer_is_a_failure_and_the_run_goes_on(answer: Any) -> None:
    project = FakeProject([make_dataset("d1", ["a"]), make_dataset("d2", ["a"])], clear_answers={"d1": answer})

    recap, _ = run(MACRO, project, {"included_tags": ["a"], **REAL_RUN})

    assert status_of(recap, "d1") == STATUS_FAILED
    assert row_of(recap, "d1")["detail"].startswith("DSS answered in an unexpected way, check the dataset")
    assert status_of(recap, "d2") == STATUS_CLEARED


def test_no_selected_dataset_still_completes_the_progress() -> None:
    recap, progress = run(MACRO, FakeProject([make_dataset("ds", ["other"])]), {"included_tags": ["a"], **REAL_RUN})

    assert recap["datasets"] == []
    assert progress == [100]


def test_the_recap_says_which_macro_ran_and_how_the_lists_match() -> None:
    recap, _ = run(MACRO, FakeProject([]), {"excluded_tags": ["k"]})

    assert (recap["macro"], recap["macro_label"]) == ("clear-datasets-by-tags", "Clear Datasets by Tags")
    assert (recap["included_match"], recap["excluded_match"]) == ("ANY", "ANY")


# The detail of selected and excluded datasets


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        ({"included_tags": ["a"], "excluded_tags": ["k"]}, {"in": "Has included tags", "both": "Has excluded tags"}),
        (
            {"included_tags": ["a"], "included_match": "ALL", "excluded_tags": ["k"], "excluded_match": "ALL"},
            {"in": "Has all included tags", "both": "Has all excluded tags"},
        ),
        ({"excluded_tags": ["k"]}, {"in": "", "both": "Has excluded tags"}),  # Without included tags, all are in.
    ],
)
def test_the_detail_says_why_a_dataset_is_selected_or_excluded(
    config: dict[str, Any], expected: dict[str, str]
) -> None:
    project = FakeProject([make_dataset("in", ["a"]), make_dataset("both", ["a", "k"])])

    recap, _ = run(MACRO, project, config)

    assert {row["name"]: row["detail"] for row in recap["datasets"]} == expected


def test_after_a_clear_the_detail_keeps_the_reason_unless_dss_says_more() -> None:
    answer = {"messages": [{"severity": "WARNING", "message": "Table was already empty"}]}
    project = FakeProject(
        [make_dataset("quiet", ["a"]), make_dataset("talkative", ["a"])], clear_answers={"talkative": answer}
    )

    recap, _ = run(MACRO, project, {"included_tags": ["a"], **REAL_RUN})

    assert row_of(recap, "quiet")["detail"] == "Has included tags"
    assert row_of(recap, "talkative")["detail"] == "WARNING: Table was already empty"


# Stopping at the first error


def test_raise_exception_stops_the_clearing_at_the_first_failure() -> None:
    project = FakeProject(
        [make_dataset(name, ["a"]) for name in ("d1", "d2", "d3", "d4")],
        clear_answers={"d2": RuntimeError("boom")},
    )

    recap, progress = run(MACRO, project, {"included_tags": ["a"], "on_error": "STOP", **REAL_RUN})

    assert project.cleared == ["d1", "d2"]
    assert [status_of(recap, name) for name in ("d1", "d2", "d3", "d4")] == [
        STATUS_CLEARED,
        STATUS_FAILED,
        STATUS_SKIPPED,
        STATUS_SKIPPED,
    ]
    assert (row_of(recap, "d3")["skip_code"], row_of(recap, "d3")["detail"]) == (
        SKIP_STOPPED,
        "Not tried: the run stopped",
    )
    assert progress == [25, 50, 75, 100]


@pytest.mark.parametrize("on_error", ["CONTINUE", "FAIL"])
def test_the_other_choices_try_every_dataset(on_error: str) -> None:
    project = FakeProject(
        [make_dataset(name, ["a"]) for name in ("d1", "d2", "d3")], clear_answers={"d1": RuntimeError("boom")}
    )

    run(MACRO, project, {"included_tags": ["a"], "on_error": on_error, **REAL_RUN})

    assert project.cleared == ["d1", "d2", "d3"]


def test_no_sharing_warning_when_the_sharing_was_read() -> None:
    project = FakeProject([make_dataset("local", ["a"])])

    recap, _ = run(MACRO, project, {"included_tags": ["a"]})

    assert row_of(recap, "local")["warnings"] == []
