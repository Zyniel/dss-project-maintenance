"""Run a macro: do its work, save its recap, log it, and return it as HTML.

This module does not import dataiku, so that it can be tested without DSS: runnable.py hands it the
API client, a way to open a dataset and the plugin settings.

Each run gets an outcome:

- SUCCESS: nothing went wrong;
- WARNING: something went wrong, and the run went on, as the form asked. DSS shows the run as a
  success: the recap shows the warning in a banner, and the log in WARNING lines;
- FAILED: something went wrong, and the form asked to fail the run ("Fail the run").
"""

import json
import logging
import time
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Optional

from dss_project_maintenance.core.macro import MaintenanceMacro
from dss_project_maintenance.core.options import FAILING_ON_ERROR, ON_ERROR_FAIL
from dss_project_maintenance.recap.dataset import write_recap_dataset
from dss_project_maintenance.recap.html import build_recap_html, dss_said, read_grid_cdn, with_outcome
from dss_project_maintenance.recap.page import OUTCOME_FAILED, OUTCOME_SUCCESS, OUTCOME_WARNING

logger = logging.getLogger(__name__)


class RunFailed(Exception):
    """Raised at the end of a run when something went wrong and the form asked to fail the run.

    That is "If an error occurs" set to "Fail the run" and a failure in the work, or "If the recap is
    not written" set to "Fail the run" and a recap dataset that could not be written.
    """


def read_run_by(client: Any) -> str:
    """Return the login of the user running the macro, or "" if DSS does not give it."""
    try:
        return str(client.get_auth_info().get("authIdentifier") or "")
    except Exception as error:
        logger.warning("Could not read who runs the macro: %s", error)
        return ""


def run_recap(
    macro: MaintenanceMacro,
    project: Any,
    project_key: str,
    config: dict[str, Any],
    progress_callback: Callable[[int], None],
    run_by: str = "",
) -> dict[str, Any]:
    """Do the work of a macro and return its recap, with the fields every recap has."""
    started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    start_time = time.time()
    logger.info("%s | project %s | run by %s", macro.label, project_key, run_by or "unknown user")

    recap = macro.run(project, project_key, config, progress_callback)
    recap.update(
        run_id=uuid.uuid4().hex,
        macro=macro.id,
        macro_label=macro.label,
        project_key=project_key,
        run_by=run_by,
        started_at=started_at,
        duration=time.time() - start_time,
        recap_dataset_result=None,
    )
    update_outcome(macro, recap)
    return recap


def save_recap(macro: MaintenanceMacro, recap: dict[str, Any], open_dataset: Callable[[str], Any]) -> dict[str, Any]:
    """Write the recap to the recap dataset. A failure is reported, not raised: the work is already done."""
    name = recap["options"]["recap_dataset"]
    result: dict[str, Any] = {"name": name, "rows_written": 0, "error": ""}
    try:
        rows = macro.build_recap_rows(recap)
        dataset = open_dataset(name)
        result["rows_written"] = write_recap_dataset(
            dataset, macro.recap_columns, rows, recap["options"]["recap_append"]
        )
        logger.info("Summary written to dataset %s: %d rows", name, result["rows_written"])
    except Exception as error:
        result["error"] = f"{type(error).__name__}: {error}"
        logger.error("The summary could not be written to dataset %s: %s", name, result["error"])
    return result


def build_problems(macro: MaintenanceMacro, recap: dict[str, Any]) -> list[dict[str, Any]]:
    """Return what went wrong in the run: the work first, then the recap dataset.

    Each problem says if it fails the run: only when its choice in the form is "Fail the run".
    """
    options = recap["options"]
    problems = []

    failures = macro.describe_failures(recap)
    if failures:
        # Only the macros that change data have "If an error occurs", in their "Run" section.
        problems.append({"message": failures, "fail": options.get("on_error") in FAILING_ON_ERROR})

    result = recap["recap_dataset_result"]
    if result and result["error"]:
        problems.append(
            {
                "message": f"Summary not written to dataset {result['name']}. {dss_said(result['error'])}",
                "fail": options.get("on_recap_error") == ON_ERROR_FAIL,
            }
        )
    return problems


def update_outcome(macro: MaintenanceMacro, recap: dict[str, Any]) -> None:
    """Set the problems and the outcome of the run in the recap. Called again after writing the recap dataset."""
    problems = build_problems(macro, recap)
    if any(problem["fail"] for problem in problems):
        outcome = OUTCOME_FAILED
    elif problems:
        outcome = OUTCOME_WARNING
    else:
        outcome = OUTCOME_SUCCESS
    recap.update(problems=problems, outcome=outcome)


def build_failure_message(recap: dict[str, Any]) -> str:
    """Return the message of a failed run: every problem, the work first, then where the details are.

    DSS shows only this message, so it also gives the problems that do not fail the run.
    """
    messages = [problem["message"] for problem in recap["problems"]]
    result = recap["recap_dataset_result"]
    written = result and not result["error"]
    details = f"Details in the summary dataset {result['name']}." if written else "Details in the run log."
    return " ".join(messages + [details])


def run_macro(
    macro: MaintenanceMacro,
    client: Any,
    project_key: str,
    config: dict[str, Any],
    progress_callback: Callable[[int], None],
    open_dataset: Callable[[str], Any],
    log_wait_seconds: float = 0.0,
    plugin_config: Optional[dict[str, Any]] = None,
) -> str:
    """Run a macro and return its HTML recap.

    :param client: client from dataiku.api_client(), acting as the user who runs the macro
    :param open_dataset: returns a dataiku.Dataset of this project from its name, for the recap dataset
    :param log_wait_seconds: pause after the last log line. DSS stops reading the log of a macro as
        soon as it returns, and a DSS 13.4.4 run lost the long RECAP_JSON line that way.
    :param plugin_config: the plugin settings, with the AG Grid a recap opened outside DSS loads
    :raises RunFailed: after the run, if something went wrong and the form asked to fail the run
    """
    run_by = read_run_by(client)
    project = client.get_project(project_key)
    recap = run_recap(macro, project, project_key, config, progress_callback, run_by)

    if recap["options"]["recap_dataset"]:
        recap["recap_dataset_result"] = save_recap(macro, recap, open_dataset)
        update_outcome(macro, recap)

    logger.info("Done in %.2f s: %s", recap["duration"], macro.describe_counts(recap))
    for problem in recap["problems"]:
        log = logger.error if problem["fail"] else logger.warning
        log("Problem: %s", problem["message"])
    logger.info("Outcome: %s", recap["outcome"])
    page = macro.build_recap_page(recap)
    # One line holds the whole recap, so that the run log alone tells what happened.
    logger.info("RECAP_JSON %s", json.dumps(with_outcome(page.summary, recap), ensure_ascii=False))
    for handler in logging.getLogger().handlers:
        handler.flush()
    time.sleep(log_wait_seconds)

    if recap["outcome"] == OUTCOME_FAILED:
        raise RunFailed(build_failure_message(recap))
    return build_recap_html(recap, page, read_grid_cdn(plugin_config))
