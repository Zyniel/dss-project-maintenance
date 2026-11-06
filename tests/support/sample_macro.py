"""A minimal macro, to test the shared code without any real macro.

It also shows the least a macro must provide. It marks each dataset of the project as done, or as
failed when its name is in config["fail"].
"""

from collections.abc import Callable
from typing import Any

from dss_project_maintenance.core.macro import MaintenanceMacro, RunStopped
from dss_project_maintenance.core.options import read_recap_options, read_run_options
from dss_project_maintenance.core.project import list_project_datasets
from dss_project_maintenance.recap.page import (
    ALL_STATUSES,
    COLUMN_STATUS,
    ICON_CHECK,
    ICON_CROSS,
    TONE_DANGER,
    TONE_SUCCESS,
    Banner,
    Column,
    Metric,
    RecapPage,
    Status,
    Table,
)

STATUS_DONE = "DONE"
STATUS_FAILED = "FAILED"
STATUSES = [
    Status(STATUS_FAILED, "Failed", TONE_DANGER, ICON_CROSS),
    Status(STATUS_DONE, "Done", TONE_SUCCESS, ICON_CHECK),
]


class SampleMacro(MaintenanceMacro):
    id = "sample-macro"
    label = "Sample Macro"
    recap_columns = ["run_id", "dataset", "status"]

    def run(
        self, project: Any, project_key: str, config: dict[str, Any], progress_callback: Callable[[int], None]
    ) -> dict[str, Any]:
        options = {**read_run_options(config), **read_recap_options(config, project_key)}
        if config.get("stop"):
            raise RunStopped("Nothing was done.")
        failing = config.get("fail") or []
        rows = [
            {"name": dataset["name"], "status": STATUS_FAILED if dataset["name"] in failing else STATUS_DONE}
            for dataset in list_project_datasets(project, project_key)
        ]
        progress_callback(100)
        return {
            "options": options,
            "notices": [],
            "blockers": [],
            "datasets": rows,
        }

    def describe_counts(self, recap: dict[str, Any]) -> str:
        return f"{len(recap['datasets'])} datasets"

    def build_recap_rows(self, recap: dict[str, Any]) -> list[list[str]]:
        return [[recap["run_id"], row["name"], row["status"]] for row in recap["datasets"]]

    def build_recap_page(self, recap: dict[str, Any]) -> RecapPage:
        columns = [Column("name", "Dataset", pinned=True), Column("status", "Status", COLUMN_STATUS)]
        table = Table("Datasets", columns, STATUSES, recap["datasets"], "No dataset.", "Search", "sample.csv")
        metrics = [Metric("Datasets", str(len(recap["datasets"])), status=ALL_STATUSES)]
        summary = {"run_id": recap["run_id"], "run_by": recap["run_by"], "datasets": recap["datasets"]}
        failures = self.describe_failures(recap)
        banners = [Banner(TONE_DANGER, failures)] if failures else []
        return RecapPage(banners, metrics, [], table, summary)

    def describe_failures(self, recap: dict[str, Any]) -> str:
        failed = [row["name"] for row in recap["datasets"] if row["status"] == STATUS_FAILED]
        return f"Failed: {', '.join(failed)}." if failed else ""


MACRO = SampleMacro()
