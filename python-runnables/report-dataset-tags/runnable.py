"""Macro "Report Dataset Tags". The logic is in python-lib, where it is tested without DSS."""

import logging
from collections.abc import Callable
from typing import Any

import dataiku
from dataiku.runnables import Runnable

from dss_maintenance.core.runner import run_macro
from dss_maintenance.macros.report_dataset_tags import MACRO

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logging.getLogger().setLevel(logging.INFO)  # basicConfig does nothing if DSS already set up logging.


class ReportDatasetTags(Runnable):
    """The macro DSS runs. The logic is in python-lib, where it is tested without DSS."""

    def __init__(self, project_key: str, config: dict[str, Any], plugin_config: dict[str, Any]) -> None:
        """Store the project the macro runs in, the values of the macro form and the plugin settings."""
        self.project_key = project_key
        self.config = config
        self.plugin_config = plugin_config

    def get_progress_target(self) -> tuple[int, str]:
        """Report the progress as a percentage."""
        return (100, "NONE")

    def run(self, progress_callback: Callable[[int], None]) -> str:
        """Run the macro and return its recap as HTML."""
        return run_macro(
            MACRO,
            dataiku.api_client(),
            self.project_key,
            self.config,
            progress_callback,
            lambda name: dataiku.Dataset(name, project_key=self.project_key, ignore_flow=True),
            log_wait_seconds=0.5,
            plugin_config=self.plugin_config,
        )
