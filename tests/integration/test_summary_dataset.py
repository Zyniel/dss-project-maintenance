"""The summary dataset on a real DSS: append mode, and a summary that cannot be written, in a scenario."""

from typing import Any

from integration.dss import REPORT, add_built_dataset, add_empty_dataset, add_macro_scenario, count_rows, run_macro


def test_append_mode_keeps_the_earlier_runs(scratch_project: Any, connection: str) -> None:
    add_built_dataset(scratch_project, "sales", ["tmp"], connection)
    add_empty_dataset(scratch_project, "summary", connection)
    config = {"recap_to_dataset": True, "recap_dataset": "summary"}

    run_macro(scratch_project, REPORT, {**config, "recap_append": True})
    one_run = count_rows(scratch_project, "summary")
    run_macro(scratch_project, REPORT, {**config, "recap_append": True})
    two_runs = count_rows(scratch_project, "summary")
    run_macro(scratch_project, REPORT, {**config, "recap_append": False})

    assert one_run > 0
    assert two_runs == 2 * one_run
    assert count_rows(scratch_project, "summary") == one_run


def test_fail_the_run_fails_the_scenario_step(scratch_project: Any, connection: str) -> None:
    add_built_dataset(scratch_project, "sales", ["tmp"], connection)
    # The macro refuses to write a summary to a dataset with other columns.
    add_empty_dataset(scratch_project, "other_columns", connection, columns=("customer_id",))
    config = {"recap_to_dataset": True, "recap_dataset": "other_columns"}
    failing = add_macro_scenario(scratch_project, "fail_the_run", REPORT, {**config, "on_recap_error": "FAIL"})
    continuing = add_macro_scenario(scratch_project, "go_on", REPORT, {**config, "on_recap_error": "CONTINUE"})

    assert failing.run_and_wait(no_fail=True).outcome == "FAILED"
    # DSS has no warning outcome for a macro: the step succeeds, the recap shows the warning.
    assert continuing.run_and_wait(no_fail=True).outcome == "SUCCESS"
    assert count_rows(scratch_project, "other_columns") == 0
