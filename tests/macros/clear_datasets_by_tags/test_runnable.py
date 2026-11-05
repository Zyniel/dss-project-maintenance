"""Tests of runnable.py, run as DSS would with a fake dataiku package: the macro works end to end."""

import logging
from typing import Any

import pytest

from dss_maintenance.core.runner import RunFailed
from dss_maintenance.macros.clear_datasets_by_tags import MACRO
from dss_maintenance.macros.clear_datasets_by_tags.recap import RECAP_COLUMNS
from support.dataiku_stub import install_fake_dataiku, load_runnable_class
from support.fakes import PROJECT_KEY, FakeClient, FakeProject, make_dataset


def run_runnable(
    monkeypatch: pytest.MonkeyPatch, project: FakeProject, config: dict[str, Any], opened: list[Any]
) -> tuple[str, list[int]]:
    install_fake_dataiku(monkeypatch, FakeClient(project), opened)
    runnable_class = load_runnable_class(MACRO.id)
    settings = {"ag_grid_url": "https://repo.example.com/ag-grid.js", "ag_grid_integrity": ""}
    runnable = runnable_class(PROJECT_KEY, config, settings)
    assert runnable.get_progress_target() == (100, "NONE")
    progress: list[int] = []
    html: str = runnable.run(progress.append)
    return html, progress


def test_the_runnable_clears_writes_the_recap_dataset_and_returns_the_recap(monkeypatch: pytest.MonkeyPatch) -> None:
    project = FakeProject([make_dataset("tmp", ["tmp"]), make_dataset("kept", ["keep"]), make_dataset("other", [])])
    opened: list[Any] = []
    config = {"excluded_tags": ["keep"], "simulate": False, "recap_dataset": "recap"}

    html, progress = run_runnable(monkeypatch, project, config, opened)

    assert project.cleared == ["other", "tmp"]
    assert "Clear Datasets by Tags · Project TEST" in html
    assert '"url": "https://repo.example.com/ag-grid.js"' in html  # The plugin settings reach the recap.
    assert progress[-1] == 100
    assert [(name, project_key, ignore_flow) for name, project_key, ignore_flow, _ in opened] == [
        ("recap", PROJECT_KEY, True)
    ]
    recap_dataset = opened[0][3]
    assert [column["name"] for column in recap_dataset.schema] == RECAP_COLUMNS
    records = [dict(zip(RECAP_COLUMNS, row)) for row in recap_dataset.rows]
    assert [(record["dataset"], record["status"]) for record in records] == [
        ("kept", "EXCLUDED"),
        ("other", "CLEARED"),
        ("tmp", "CLEARED"),
    ]
    assert "Summary written to dataset recap: 3 rows." in html


def test_on_error_fail_names_the_failed_datasets(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    project = FakeProject(
        [make_dataset("d1", ["a"]), make_dataset("d2", ["a"]), make_dataset("d3", ["a"])],
        clear_answers={"d2": RuntimeError("locked")},
    )
    config = {"included_tags": ["a"], "simulate": False, "on_error": "FAIL"}

    with pytest.raises(RunFailed, match=r"^1 of 3 datasets to clear failed: d2\. The other 2 were cleared\."):
        run_runnable(monkeypatch, project, config, [])

    assert project.cleared == ["d1", "d2", "d3"]
    done = [record.getMessage() for record in caplog.records if record.getMessage().startswith("Done in ")]
    assert len(done) == 1
    assert done[0].endswith(": 2 cleared, 1 failed, 0 skipped, 0 excluded, out of 3 selected and 3 scanned datasets")


def test_raise_exception_fails_the_run_at_the_first_error(monkeypatch: pytest.MonkeyPatch) -> None:
    project = FakeProject(
        [make_dataset("d1", ["a"]), make_dataset("d2", ["a"]), make_dataset("d3", ["a"])],
        clear_answers={"d1": RuntimeError("locked")},
    )
    config = {"included_tags": ["a"], "simulate": False, "on_error": "STOP"}

    with pytest.raises(
        RunFailed,
        match=r"^1 of 1 dataset to clear failed: d1\. The run stopped at the first error: 2 datasets were not tried\.",
    ):
        run_runnable(monkeypatch, project, config, [])

    assert project.cleared == ["d1"]
