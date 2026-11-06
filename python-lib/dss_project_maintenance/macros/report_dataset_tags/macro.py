"""The MaintenanceMacro of "Report Dataset Tags": what the shared runner calls."""

from collections.abc import Callable
from typing import Any

from dss_project_maintenance.core.macro import MaintenanceMacro
from dss_project_maintenance.macros.report_dataset_tags.recap import (
    RECAP_COLUMNS,
    build_recap_page,
    build_recap_rows,
    describe_counts,
    describe_failures,
)
from dss_project_maintenance.macros.report_dataset_tags.report import run_report
from dss_project_maintenance.recap.page import RecapPage


class ReportDatasetTagsMacro(MaintenanceMacro):
    """Reports how the datasets of a project use tags. It changes nothing.

    Each method calls the function of the same name in report.py or recap.py.
    """

    id = "report-dataset-tags"
    label = "Report Dataset Tags"
    recap_columns = RECAP_COLUMNS

    def run(
        self, project: Any, project_key: str, config: dict[str, Any], progress_callback: Callable[[int], None]
    ) -> dict[str, Any]:
        return run_report(project, project_key, config, progress_callback)

    def describe_counts(self, recap: dict[str, Any]) -> str:
        return describe_counts(recap)

    def build_recap_rows(self, recap: dict[str, Any]) -> list[list[str]]:
        return build_recap_rows(recap)

    def build_recap_page(self, recap: dict[str, Any]) -> RecapPage:
        return build_recap_page(recap)

    def describe_failures(self, recap: dict[str, Any]) -> str:
        return describe_failures(recap)


MACRO = ReportDatasetTagsMacro()
