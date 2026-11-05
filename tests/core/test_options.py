"""Tests of reading a macro form: checkboxes, and the options of the "Run" and "Summary" sections."""

from typing import Any

import pytest

from dss_maintenance.core.options import (
    RECAP_ERROR_CHOICES,
    RECAP_OPTION_DEFAULTS,
    RUN_ERROR_CHOICES,
    RUN_OPTION_DEFAULTS,
    read_checkbox,
    read_choice,
    read_recap_options,
    read_run_options,
)
from support.fakes import PROJECT_KEY


@pytest.mark.parametrize(
    ("value", "expected"), [(True, True), (False, False), (None, True), ("false", True), (0, True)]
)
def test_only_a_real_boolean_changes_a_checkbox_checked_by_default(value: Any, expected: bool) -> None:
    assert read_checkbox({"option": value}, "option", True) is expected


@pytest.mark.parametrize(
    ("value", "expected"), [(True, True), (False, False), (None, False), ("true", False), (1, False)]
)
def test_only_a_real_boolean_changes_a_checkbox_unchecked_by_default(value: Any, expected: bool) -> None:
    assert read_checkbox({"option": value}, "option", False) is expected


def test_a_missing_checkbox_takes_its_default() -> None:
    assert read_checkbox({}, "option", True) is True


@pytest.mark.parametrize("value", ["CONTINUE", "FAIL", "STOP"])
def test_a_choice_of_the_list_is_kept(value: str) -> None:
    assert read_choice({"choice": value}, "choice", RUN_ERROR_CHOICES, "CONTINUE") == value


@pytest.mark.parametrize("value", [None, "", "fail", "Raise exception", True, 1, ["FAIL"]])
def test_a_value_that_is_not_a_choice_gives_the_default(value: Any) -> None:
    assert read_choice({"choice": value}, "choice", RUN_ERROR_CHOICES, "CONTINUE") == "CONTINUE"


def test_the_error_choices() -> None:
    # DSS shows a macro run as a success or a failure, never as a warning.
    assert RUN_ERROR_CHOICES == {
        "CONTINUE": "Continue, run ends as success",
        "FAIL": "Continue, run ends in error",
        "STOP": "Raise exception",
    }
    # Writing the summary is the last step: there is nothing left to stop.
    assert RECAP_ERROR_CHOICES == {"CONTINUE": "Continue", "FAIL": "Fail the run"}


# The "Run" section


def test_run_options_continue_on_errors_by_default() -> None:
    assert read_run_options({}) == RUN_OPTION_DEFAULTS == {"on_error": "CONTINUE"}


@pytest.mark.parametrize("value", ["FAIL", "STOP"])
def test_on_error_can_fail_the_run(value: str) -> None:
    assert read_run_options({"on_error": value}) == {"on_error": value}


def test_the_old_checkbox_fail_on_error_is_ignored() -> None:
    assert read_run_options({"fail_on_error": True}) == {"on_error": "CONTINUE"}


# The "Summary" section


def test_recap_options_default_to_no_recap_dataset() -> None:
    assert read_recap_options({}, PROJECT_KEY) == {**RECAP_OPTION_DEFAULTS, "recap_dataset": None}


def test_recap_options_hold_no_run_option() -> None:
    assert "on_error" not in read_recap_options({"on_error": "FAIL"}, PROJECT_KEY)


def test_on_recap_error_continues_by_default_and_can_fail_the_run() -> None:
    assert read_recap_options({}, PROJECT_KEY)["on_recap_error"] == "CONTINUE"
    assert read_recap_options({"on_recap_error": "FAIL"}, PROJECT_KEY)["on_recap_error"] == "FAIL"
    assert read_recap_options({"on_recap_error": "STOP"}, PROJECT_KEY)["on_recap_error"] == "CONTINUE"


@pytest.mark.parametrize("value", [None, "false", 0, "no"])
def test_only_a_real_false_drops_the_earlier_runs(value: Any) -> None:
    assert read_recap_options({"recap_append": value}, PROJECT_KEY)["recap_append"] is True


@pytest.mark.parametrize(("value", "expected"), [("recap", "recap"), ("TEST.recap", "recap"), ("", None), (None, None)])
def test_recap_dataset_name(value: Any, expected: Any) -> None:
    assert read_recap_options({"recap_dataset": value}, PROJECT_KEY)["recap_dataset"] == expected


@pytest.mark.parametrize(("value", "expected"), [(True, "recap"), (None, "recap"), ("false", "recap"), (False, None)])
def test_only_a_real_false_turns_the_recap_dataset_off(value: Any, expected: Any) -> None:
    options = read_recap_options({"recap_to_dataset": value, "recap_dataset": "recap"}, PROJECT_KEY)
    assert (options["recap_to_dataset"], options["recap_dataset"]) == (expected is not None, expected)


def test_writing_the_recap_to_a_dataset_needs_a_dataset() -> None:
    with pytest.raises(ValueError, match="Pick a summary dataset, or uncheck 'Write to a dataset'"):
        read_recap_options({"recap_to_dataset": True, "recap_dataset": ""}, PROJECT_KEY)


def test_recap_dataset_of_another_project_is_refused() -> None:
    with pytest.raises(ValueError, match="must belong to this project"):
        read_recap_options({"recap_dataset": "OTHER.recap"}, PROJECT_KEY)
