"""What every macro of the plugin provides, so that the shared code can run it and show its recap."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from dss_project_maintenance.recap.page import RecapPage


class RunStopped(Exception):
    """Raised before changing anything, when a real run must not go on."""


class MaintenanceMacro(ABC):
    """A macro of the plugin. Each macro package defines a subclass, and one instance of it named MACRO.

    The recap is a dict. run() returns it, with at least:

    - "options": the options of the form, including those of read_recap_options(), and of
      read_run_options() for a macro that changes data;
    - "notices": what the reader must know, the run went on, as a list of Banner;
    - "blockers": why a real run would stop. Only a simulation returns with blockers.

    A macro that changes data also returns "simulate": True when the run changed nothing. A macro
    that only reads, such as a report, has no simulation.

    The runner then adds the fields every recap has: run_id, macro, macro_label, project_key, run_by,
    started_at, duration, recap_dataset_result, problems and outcome.
    """

    id: str  # Its folder in python-runnables.
    label: str  # Its name on the Macros page, as in its runnable.json.
    recap_columns: list[str]  # The columns of its recap dataset.

    @abstractmethod
    def run(
        self, project: Any, project_key: str, config: dict[str, Any], progress_callback: Callable[[int], None]
    ) -> dict[str, Any]:
        """Do the work and return the recap.

        :param project: project handle from dataiku.api_client()
        :param config: values of the macro form
        :param progress_callback: called with the percentage of the work done
        :raises ValueError: if the form is not valid, before changing anything
        :raises RunStopped: in a real run, if a check fails, before changing anything
        """

    @abstractmethod
    def describe_counts(self, recap: dict[str, Any]) -> str:
        """Return the totals of the run for the log, such as "2 cleared, 1 failed"."""

    @abstractmethod
    def build_recap_rows(self, recap: dict[str, Any]) -> list[list[str]]:
        """Return the rows of the recap dataset, as texts in the order of recap_columns."""

    @abstractmethod
    def build_recap_page(self, recap: dict[str, Any]) -> RecapPage:
        """Return what the HTML recap shows, with the recap as plain JSON data in its summary.

        The runner writes that summary on the RECAP_JSON line of the log, and the HTML recap holds it
        in a hidden block, for the API.
        """

    @abstractmethod
    def describe_failures(self, recap: dict[str, Any]) -> str:
        """Return what failed in the work as counts, such as "1 of 3 datasets failed, 2 cleared.", or "".

        The runner logs it, and fails the run with it when "If an error occurs" is "Fail the run". When
        the run goes on, DSS shows a success, so build_recap_page() must show the failure in a banner.
        The runner handles the recap dataset itself. A macro that only reads returns "".
        """
