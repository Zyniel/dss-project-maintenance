"""Tests of the shared runner, with a minimal macro: the recap fields, the recap dataset, the log, failing the run."""

import json
import logging
from typing import Any, Optional

import pytest

from dss_maintenance.core.macro import RunStopped
from dss_maintenance.core.runner import RunFailed, run_macro
from support.fakes import PROJECT_KEY, FakeClient, FakeProject, FakeRecapDataset, make_dataset
from support.runs import run
from support.sample_macro import MACRO


def run_with(
    project: FakeProject,
    config: dict[str, Any],
    recap_dataset: Optional[FakeRecapDataset] = None,
    client: Optional[FakeClient] = None,
    plugin_config: Optional[dict[str, Any]] = None,
) -> str:
    opened: list[str] = []

    def open_dataset(name: str) -> FakeRecapDataset:
        opened.append(name)
        assert recap_dataset is not None, "no recap dataset expected"
        return recap_dataset

    html = run_macro(
        MACRO,
        client or FakeClient(project),
        PROJECT_KEY,
        config,
        lambda _: None,
        open_dataset,
        plugin_config=plugin_config,
    )
    wanted = config.get("recap_dataset") if config.get("recap_to_dataset") is not False else None
    assert opened == ([wanted] if wanted else [])
    return html


def logged_summary(caplog: pytest.LogCaptureFixture) -> dict[str, Any]:
    lines = [record.getMessage() for record in caplog.records if record.getMessage().startswith("RECAP_JSON ")]
    assert len(lines) == 1
    summary: dict[str, Any] = json.loads(lines[0][len("RECAP_JSON ") :])
    return summary


def test_the_recap_says_which_macro_ran_who_ran_it_and_when() -> None:
    recap, progress = run(MACRO, FakeProject([make_dataset("ds", [])]), {})

    assert (recap["macro"], recap["macro_label"], recap["project_key"]) == ("sample-macro", "Sample Macro", "TEST")
    assert recap["run_by"] == "jdoe"
    assert len(recap["run_id"]) == 32
    assert len(recap["started_at"]) == len("2026-11-02T19:10:00Z")
    assert recap["started_at"].endswith("Z")
    assert recap["duration"] >= 0
    assert recap["recap_dataset_result"] is None
    assert progress == [100]


def test_the_run_returns_the_html_recap_and_logs_the_summary(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)

    html = run_with(FakeProject([make_dataset("ds", [])]), {})

    assert "Sample Macro · Project TEST · Run by jdoe" in html
    assert logged_summary(caplog)["datasets"] == [{"name": "ds", "status": "DONE"}]
    assert any(record.getMessage().startswith("Done in ") for record in caplog.records)


def test_the_run_goes_on_when_dss_does_not_say_who_runs_it() -> None:
    project = FakeProject([make_dataset("ds", [])])

    html = run_with(project, {}, client=FakeClient(project, auth_error=RuntimeError("no auth")))

    assert "Run by unknown user" in html


def test_the_recap_is_written_to_the_recap_dataset_with_the_columns_of_the_macro() -> None:
    recap_dataset = FakeRecapDataset()

    html = run_with(
        FakeProject([make_dataset("d1", []), make_dataset("d2", [])]), {"recap_dataset": "r"}, recap_dataset
    )

    assert [column["name"] for column in recap_dataset.schema] == MACRO.recap_columns
    assert [row[1:] for row in recap_dataset.rows] == [["d1", "DONE"], ["d2", "DONE"]]
    assert "Summary written to dataset r: 2 rows." in html


def test_the_recap_dataset_keeps_the_earlier_runs() -> None:
    recap_dataset = FakeRecapDataset()

    run_with(FakeProject([make_dataset("ds", [])]), {"recap_dataset": "r"}, recap_dataset)
    run_with(FakeProject([make_dataset("ds", [])]), {"recap_dataset": "r"}, recap_dataset)

    assert len(recap_dataset.rows) == 2
    assert recap_dataset.rows[0][0] != recap_dataset.rows[1][0]


def test_unchecking_write_the_recap_to_a_dataset_ignores_the_dataset_picked_before() -> None:
    html = run_with(FakeProject([make_dataset("ds", [])]), {"recap_to_dataset": False, "recap_dataset": "r"})

    assert "Recap written" not in html


# The outcome of the run, and the two choices for errors


def test_a_run_with_no_problem_has_the_outcome_success(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)

    html = run_with(FakeProject([make_dataset("ds", [])]), {"on_error": "FAIL", "on_recap_error": "FAIL"})

    summary = logged_summary(caplog)
    assert (summary["outcome"], summary["problems"]) == ("SUCCESS", [])
    assert "dtp-banner" not in html.split("</style>")[1]  # No banner at all.


def test_a_failed_item_fails_the_run_by_default() -> None:
    with pytest.raises(RunFailed, match=r"^Failed: d2\."):
        run_with(FakeProject([make_dataset("d1", []), make_dataset("d2", [])]), {"fail": ["d2"]})


def test_continue_gives_a_warning_after_a_failed_item(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)

    html = run_with(
        FakeProject([make_dataset("d1", []), make_dataset("d2", [])]), {"fail": ["d2"], "on_error": "CONTINUE"}
    )

    assert '<div class="dtp-banner"><strong>Warning: the run went on after these errors:</strong>' in html
    assert "<li>Failed: d2.</li>" in html
    assert logged_summary(caplog)["outcome"] == "WARNING"
    assert [(r.levelname, r.getMessage()) for r in caplog.records if r.getMessage().startswith("Problem")] == [
        ("WARNING", "Problem: Failed: d2.")
    ]


def test_on_error_fail_fails_the_run_after_the_work(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    project = FakeProject([make_dataset("d1", []), make_dataset("d2", [])])

    with pytest.raises(RunFailed, match=r"^Failed: d2\. The full recap is in the run log"):
        run_with(project, {"fail": ["d2"], "on_error": "FAIL"})

    summary = logged_summary(caplog)  # The run log has the recap anyway.
    assert (len(summary["datasets"]), summary["outcome"]) == (2, "FAILED")
    assert any(r.levelname == "ERROR" and r.getMessage() == "Problem: Failed: d2." for r in caplog.records)


def test_a_recap_dataset_not_written_gives_a_warning_by_default() -> None:
    recap_dataset = FakeRecapDataset(["customer_id"], [["c1"]])

    html = run_with(FakeProject([make_dataset("ds", [])]), {"recap_dataset": "r"}, recap_dataset)

    assert "Warning: the run went on after these errors:" in html
    assert "<li>The summary could not be written to dataset r: ValueError: it already holds other columns" in html
    assert "an earlier run wrote to.</li>" in html  # One period, though the error ends with one.
    assert recap_dataset.rows == [["c1"]]


def test_on_recap_error_fail_fails_the_run() -> None:
    recap_dataset = FakeRecapDataset(write_error=OSError("disk full"))
    config = {"on_recap_error": "FAIL", "recap_dataset": "r"}

    with pytest.raises(
        RunFailed, match=r"^The summary could not be written to dataset r: OSError: disk full\. The full"
    ):
        run_with(FakeProject([make_dataset("ds", [])]), config, recap_dataset)


def test_on_error_fail_does_not_cover_the_recap_dataset() -> None:
    recap_dataset = FakeRecapDataset(write_error=OSError("disk full"))
    config = {"on_error": "FAIL", "recap_dataset": "r"}

    html = run_with(FakeProject([make_dataset("ds", [])]), config, recap_dataset)

    assert "Warning: the run went on after these errors:" in html


def test_both_problems_make_one_message_the_work_first() -> None:
    recap_dataset = FakeRecapDataset(write_error=OSError("disk full"))
    config = {"fail": ["ds"], "on_error": "FAIL", "on_recap_error": "FAIL", "recap_dataset": "r"}

    with pytest.raises(RunFailed, match=r"^Failed: ds\. The summary could not be written to dataset r: OSError: disk"):
        run_with(FakeProject([make_dataset("ds", [])]), config, recap_dataset)


def test_a_failed_run_message_also_gives_the_problems_that_do_not_fail_it() -> None:
    recap_dataset = FakeRecapDataset(write_error=OSError("disk full"))
    config = {"fail": ["ds"], "on_error": "CONTINUE", "on_recap_error": "FAIL", "recap_dataset": "r"}

    with pytest.raises(RunFailed, match=r"^Failed: ds\. The summary could not be written"):
        run_with(FakeProject([make_dataset("ds", [])]), config, recap_dataset)


def test_fail_the_run_returns_the_recap_when_everything_worked() -> None:
    html = run_with(FakeProject([make_dataset("ds", [])]), {"on_error": "FAIL"})

    assert "Sample Macro · Project TEST" in html


def test_a_stopped_run_writes_no_recap() -> None:
    recap_dataset = FakeRecapDataset()

    with pytest.raises(RunStopped):
        run_with(FakeProject([make_dataset("ds", [])]), {"stop": True, "recap_dataset": "r"}, recap_dataset)

    assert (recap_dataset.schema, recap_dataset.rows) == ([], [])


def test_the_plugin_settings_choose_the_ag_grid_of_a_downloaded_recap() -> None:
    settings = {"ag_grid_url": "https://repo.example.com/ag-grid.js", "ag_grid_integrity": ""}

    html = run_with(FakeProject([make_dataset("ds", [])]), {}, plugin_config=settings)

    assert '"url": "https://repo.example.com/ag-grid.js"' in html


def test_raise_exception_also_fails_the_run(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)

    with pytest.raises(RunFailed, match=r"^Failed: d1\."):
        run_with(FakeProject([make_dataset("d1", [])]), {"fail": ["d1"], "on_error": "STOP"})

    assert logged_summary(caplog)["outcome"] == "FAILED"


def test_the_page_and_its_summary_are_built_once(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    caplog.set_level(logging.INFO)
    calls: list[str] = []
    build_recap_page = MACRO.build_recap_page

    def counted(recap: dict[str, Any]) -> Any:
        calls.append(recap["run_id"])
        return build_recap_page(recap)

    monkeypatch.setattr(MACRO, "build_recap_page", counted)

    html = run_with(FakeProject([make_dataset("ds", [])]), {})

    assert len(calls) == 1
    # The log and the HTML hold the same summary, with the outcome.
    assert logged_summary(caplog)["run_id"] == calls[0]
    assert f'"run_id": "{calls[0]}"' in html
