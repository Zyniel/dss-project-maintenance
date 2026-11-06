"""Tests of runnable.py, run as DSS would with a fake dataiku package: the macro works end to end."""

from typing import Any

import pytest

from dss_project_maintenance.core.runner import RunFailed, run_macro
from dss_project_maintenance.macros.report_dataset_tags import MACRO
from dss_project_maintenance.macros.report_dataset_tags.recap import RECAP_COLUMNS
from support.dataiku_stub import install_fake_dataiku, load_runnable_class
from support.fakes import PROJECT_KEY, FakeClient, FakeProject, FakeRecapDataset, make_dataset


def test_the_runnable_reports_writes_the_recap_dataset_and_changes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    project = FakeProject(
        [make_dataset("a", ["tmp", "Stage:Raw"]), make_dataset("b", [])], tag_categories={"Stage": ["Raw"]}
    )
    opened: list[Any] = []
    install_fake_dataiku(monkeypatch, FakeClient(project), opened)
    runnable = load_runnable_class(MACRO.id)(PROJECT_KEY, {"recap_dataset": "recap"}, {})
    progress: list[int] = []

    html = runnable.run(progress.append)

    assert "Report Dataset Tags · Project TEST" in html
    assert progress == [100]
    assert project.cleared == []
    recap_dataset = opened[0][3]
    assert [column["name"] for column in recap_dataset.schema] == RECAP_COLUMNS
    records = [dict(zip(RECAP_COLUMNS, row)) for row in recap_dataset.rows]
    assert [(record["tag"], record["dataset"]) for record in records] == [("Stage:Raw", "a"), ("tmp", "a"), ("", "b")]
    assert "<strong>Summary written.</strong> 3 rows in dataset recap." in html


def test_on_error_sent_through_the_api_is_ignored() -> None:
    project = FakeProject([make_dataset("a", ["tmp"])])
    config = {"on_error": "FAIL", "recap_dataset": "recap"}

    html = run_macro(
        MACRO, FakeClient(project), PROJECT_KEY, config, lambda _: None, lambda _: FakeRecapDataset(["other"])
    )

    assert "<strong>Summary not written.</strong> Dataset recap." in html
    assert "If an error occurs" not in html


def test_on_recap_error_fail_fails_the_report_when_the_recap_dataset_cannot_be_written() -> None:
    project = FakeProject([make_dataset("a", ["tmp"])])
    config = {"on_recap_error": "FAIL", "recap_dataset": "recap"}

    with pytest.raises(RunFailed, match="^Summary not written to dataset recap"):
        run_macro(
            MACRO, FakeClient(project), PROJECT_KEY, config, lambda _: None, lambda _: FakeRecapDataset(["other"])
        )
