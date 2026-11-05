"""The MaintenanceMacro of "Clear Datasets by Tags": what the shared runner calls."""

from collections.abc import Callable
from typing import Any

from dss_maintenance.core.macro import MaintenanceMacro
from dss_maintenance.macros.clear_datasets_by_tags.cleanup import run_cleanup
from dss_maintenance.macros.clear_datasets_by_tags.recap import (
    RECAP_COLUMNS,
    build_recap_page,
    build_recap_rows,
    describe_counts,
    describe_failures,
)
from dss_maintenance.recap.page import RecapPage


class ClearDatasetsByTagsMacro(MaintenanceMacro):
    """Clears the data of the datasets matching the included tags and not the excluded ones.

    Each method calls the function of the same name in cleanup.py or recap.py.
    """

    id = "clear-datasets-by-tags"
    label = "Clear Datasets by Tags"
    recap_columns = RECAP_COLUMNS

    def run(
        self, project: Any, project_key: str, config: dict[str, Any], progress_callback: Callable[[int], None]
    ) -> dict[str, Any]:
        return run_cleanup(project, project_key, config, progress_callback)

    def describe_counts(self, recap: dict[str, Any]) -> str:
        return describe_counts(recap)

    def build_recap_rows(self, recap: dict[str, Any]) -> list[list[str]]:
        return build_recap_rows(recap)

    def build_recap_page(self, recap: dict[str, Any]) -> RecapPage:
        return build_recap_page(recap)

    def describe_failures(self, recap: dict[str, Any]) -> str:
        return describe_failures(recap)


MACRO = ClearDatasetsByTagsMacro()
