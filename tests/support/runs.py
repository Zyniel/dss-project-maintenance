"""Run a macro on a fake project, as the shared runner does, and read its recap."""

from typing import Any

from dss_project_maintenance.core.macro import MaintenanceMacro
from dss_project_maintenance.core.runner import run_recap
from support.fakes import PROJECT_KEY, FakeProject


def run(macro: MaintenanceMacro, project: FakeProject, config: dict[str, Any]) -> tuple[dict[str, Any], list[int]]:
    """Run a macro on the fake project and return its recap and the progress it reported."""
    progress: list[int] = []
    recap = run_recap(macro, project, PROJECT_KEY, config, progress.append, run_by="jdoe")
    return recap, progress


def row_of(recap: dict[str, Any], name: str) -> dict[str, Any]:
    """Return the recap row of a dataset."""
    rows: list[dict[str, Any]] = recap["datasets"]
    for row in rows:
        if row["name"] == name:
            return row
    raise AssertionError(f"{name} is not in the recap")


def status_of(recap: dict[str, Any], name: str) -> str:
    """Return the status of a dataset in the recap."""
    status: str = row_of(recap, name)["status"]
    return status
