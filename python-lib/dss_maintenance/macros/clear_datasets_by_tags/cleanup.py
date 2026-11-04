"""Clear the data of the datasets selected by their tags.

A run has two steps. Step 1 decides what to do with each dataset, before clearing anything, so that
any reason to stop is found while nothing is cleared yet. Step 2 clears the datasets, one by one.
"""

import logging
import time
from collections.abc import Callable
from typing import Any, Optional

from dss_maintenance.core.macro import RunStopped
from dss_maintenance.core.options import (
    ON_ERROR_STOP,
    option_unchecked,
    read_checkbox,
    read_recap_options,
    read_run_options,
)
from dss_maintenance.core.project import (
    list_project_datasets,
    name_projects,
    read_datasets_without_recipe,
    read_shared_datasets,
)
from dss_maintenance.core.tags import (
    TaggedDataset,
    TagSelection,
    count_datasets_with_tag,
    describe_match,
    read_tag_selection,
    select_datasets,
    tags_in_both,
)

logger = logging.getLogger(__name__)

STATUS_CLEARED = "CLEARED"
STATUS_WOULD_BE_CLEARED = "WOULD_BE_CLEARED"
STATUS_FAILED = "FAILED"
STATUS_SKIPPED = "SKIPPED"
STATUS_EXCLUDED = "EXCLUDED"
STATUS_LABELS = {
    STATUS_CLEARED: "Cleared",
    STATUS_WOULD_BE_CLEARED: "Would be cleared",
    STATUS_FAILED: "Failed",
    STATUS_SKIPPED: "Skipped",
    STATUS_EXCLUDED: "Excluded",
}

# Why a dataset is skipped, for the readers of the recap dataset and of the JSON recap.
SKIP_RECAP_DATASET = "RECAP_DATASET"
SKIP_EXTERNAL = "EXTERNAL"
SKIP_SHARED = "SHARED"
SKIP_PARTITIONED = "PARTITIONED"
SKIP_WITHOUT_RECIPE = "WITHOUT_RECIPE"
SKIP_STOPPED = "STOPPED"  # Not tried: "If an error occurs" is "Raise exception", and a clear failed before.

# Default value and label of the options of this macro, as in its form. A test checks that the form
# agrees. The options of the "Run" and "Summary" sections are in core/options.py.
OPTION_DEFAULTS = {
    "simulate": True,
    "purge_shared": True,
    "purge_partitioned": False,
    "purge_without_recipe": False,
}
OPTION_LABELS = {
    "simulate": "Simulate",
    "purge_shared": "Clear shared datasets",
    "purge_partitioned": "Clear partitioned datasets",
    "purge_without_recipe": "Clear datasets with no recipe",
}


def read_options(config: dict[str, Any], project_key: str) -> dict[str, Any]:
    """Return the options of the form.

    Any value that is not a real true or false gives the default: a simulation, shared datasets
    cleared, partitioned and recipe-less datasets skipped, and the earlier runs kept in the summary
    dataset.
    """
    options = {name: read_checkbox(config, name, default) for name, default in OPTION_DEFAULTS.items()}
    options.update(read_run_options(config))
    options.update(read_recap_options(config, project_key))
    return options


def decide(
    tagged: TaggedDataset,
    selection: TagSelection,
    options: dict[str, Any],
    shared_datasets: Optional[dict[str, list[str]]],
    datasets_without_recipe: Optional[set[str]],
) -> dict[str, Any]:
    """Decide what to do with one selected dataset, and why. Nothing is cleared here.

    A dataset to clear gets the status "would be cleared": step 2 clears it unless the run is a simulation.
    The detail says why it is selected, excluded or skipped.
    """
    dataset = tagged.dataset
    name = dataset["name"]
    connection = (dataset.get("params") or {}).get("connection") or ""
    dimensions = [
        dimension.get("name", "") for dimension in (dataset.get("partitioning") or {}).get("dimensions") or []
    ]

    is_shared = None if shared_datasets is None else name in shared_datasets
    shared_with = (shared_datasets or {}).get(name, [])
    built_by_recipe = None if datasets_without_recipe is None else name not in datasets_without_recipe

    row: dict[str, Any] = {
        "name": name,
        "type": dataset.get("type") or "",
        "connection": connection,
        "included_tags": tagged.included_tags,
        "excluded_tags": tagged.excluded_tags,
        "is_shared": is_shared,
        "shared_with": shared_with,
        "built_by_recipe": built_by_recipe,
        "partition_dimensions": dimensions,
        "status": STATUS_WOULD_BE_CLEARED,
        "skip_code": "",
        # Without included tags, every dataset is selected: there is nothing to say.
        "detail": describe_match("included", selection.included_match) if selection.included_tags else "",
        "warnings": [],
        "duration": None,
    }

    def skip(code: str, reason: str) -> dict[str, Any]:
        row.update(status=STATUS_SKIPPED, skip_code=code, detail=reason)
        return row

    if tagged.is_excluded:
        row.update(status=STATUS_EXCLUDED, detail=describe_match("excluded", selection.excluded_match))
        return row
    if name == options["recap_dataset"]:
        return skip(SKIP_RECAP_DATASET, "Is the summary dataset")
    if dataset.get("managed") is not True:
        # DSS does not manage the data of an external dataset, so it is never cleared.
        return skip(SKIP_EXTERNAL, f"Is external (connection {connection})" if connection else "Is external")
    if is_shared and not options["purge_shared"]:
        unchecked = option_unchecked(OPTION_LABELS["purge_shared"])
        return skip(SKIP_SHARED, f"Is shared with {name_projects(shared_with)}; {unchecked}")
    if dimensions and not options["purge_partitioned"]:
        unchecked = option_unchecked(OPTION_LABELS["purge_partitioned"])
        return skip(SKIP_PARTITIONED, f"Is partitioned by {', '.join(dimensions)}; {unchecked}")
    if built_by_recipe is False and not options["purge_without_recipe"]:
        return skip(SKIP_WITHOUT_RECIPE, f"Has no recipe; {option_unchecked(OPTION_LABELS['purge_without_recipe'])}")

    # Cleared: warn about what the reader may not expect.
    if is_shared:
        row["warnings"].append(f"Shared with {name_projects(shared_with)}: the projects using it can break")
    if is_shared is None:
        row["warnings"].append("Sharing not checked: other projects may use it")
    if dimensions:
        row["warnings"].append(f"All partitions are cleared (partitioned by {', '.join(dimensions)})")
    if built_by_recipe is False:
        row["warnings"].append("No recipe builds it: its data cannot be rebuilt")
    return row


def read_clear_response(response: Any) -> tuple[str, str]:
    """Return the status and the messages of DSS after a clear.

    clear() does not raise when DSS cannot clear the data: the HTTP call still succeeds and only the
    response says so. Do not read "success" here: it is also false after a clear that worked, when
    DSS has no message to give.
    """
    if not isinstance(response, dict):
        raise TypeError(f"unexpected answer {str(response)[:200]!r}")

    messages = []
    for message in response.get("messages") or []:
        text = message.get("details") or message.get("message") or ""
        severity = message.get("severity") or ""
        if text:
            messages.append(f"{severity}: {text}" if severity else text)
    detail = " | ".join(messages)

    if response.get("error") or response.get("fatal"):
        return STATUS_FAILED, detail or "DSS reported an error without any message."
    return STATUS_CLEARED, detail


def clear_dataset(project: Any, dataset_name: str) -> tuple[str, str, float]:
    """Clear one dataset. A failure is reported, not raised, so the run can go on with the next datasets.

    :returns: the status, the messages of DSS or the error, and the duration in seconds
    """
    start_time = time.time()
    try:
        response = project.get_dataset(dataset_name).clear()
    except Exception as error:
        return STATUS_FAILED, f"{type(error).__name__}: {error}", time.time() - start_time
    duration = time.time() - start_time

    logger.info("Clear response for dataset %s: %s", dataset_name, response)
    try:
        status, detail = read_clear_response(response)
    except Exception as error:
        return STATUS_FAILED, f"DSS answered in an unexpected way, check the dataset: {error}", duration
    return status, detail, duration


def count_by_status(rows: list[dict[str, Any]]) -> dict[str, int]:
    """Return the number of datasets per status, with every status present."""
    counts = dict.fromkeys(STATUS_LABELS, 0)
    for row in rows:
        counts[row["status"]] += 1
    return counts


def describe_row(row: dict[str, Any]) -> str:
    """Return the status of a dataset with its detail and warnings, for the log."""
    text = f"{row['name']}: {STATUS_LABELS[row['status']]}"
    if row["detail"]:
        text += f" - {row['detail']}"
    for warning in row["warnings"]:
        text += f" - warning: {warning}"
    return text


def run_cleanup(
    project: Any, project_key: str, config: dict[str, Any], progress_callback: Callable[[int], None]
) -> dict[str, Any]:
    """Clear the selected datasets and return what the recap needs.

    :param project: project handle from dataiku.api_client()
    :param project_key: key of this project
    :param config: values of the macro form
    :param progress_callback: called with the percentage of datasets processed
    :raises ValueError: if the form is not valid, before clearing anything
    :raises RunStopped: in a real run, if a check fails, before clearing anything
    """
    selection = read_tag_selection(config)
    options = read_options(config, project_key)
    simulate = options["simulate"]

    logger.info("%s", "Simulation, nothing is cleared" if simulate else "Real run, data is cleared")
    logger.info(
        "Included tags (%s): %s | excluded tags (%s): %s",
        selection.included_match,
        selection.included_tags or "none",
        selection.excluded_match,
        selection.excluded_tags or "none",
    )
    logger.info("Options: %s", options)

    # Step 1: decide what to do with each dataset, before clearing anything.
    project_datasets = list_project_datasets(project, project_key)
    notices: list[str] = []  # What the reader must know. The run goes on.
    blockers: list[str] = []  # Why a real run stops before clearing anything. A simulation shows them.

    shared_datasets: Optional[dict[str, list[str]]] = None
    try:
        shared_datasets = read_shared_datasets(project)
    except Exception as error:
        problem = (
            f"DSS did not give the datasets shared with other projects ({error}). "
            "Only project administrators can read them."
        )
        if options["purge_shared"]:
            notices.append(f"Sharing not checked. {problem} Shared datasets are cleared like the others.")
        else:
            blockers.append(
                f"Shared datasets cannot be skipped. {problem} "
                f"Ask a project administrator to run the macro, or check '{OPTION_LABELS['purge_shared']}'."
            )

    datasets_without_recipe: Optional[set[str]] = None
    try:
        datasets_without_recipe = read_datasets_without_recipe(project)
    except Exception as error:
        problem = f"Reading the Flow failed ({error})."
        if options["purge_without_recipe"]:
            notices.append(f"Recipes not checked. {problem} Datasets no recipe builds are cleared like the others.")
        else:
            blockers.append(
                f"Datasets no recipe builds cannot be skipped. {problem} "
                f"Run the macro again, or check '{OPTION_LABELS['purge_without_recipe']}'."
            )

    in_both = tags_in_both(selection)
    if in_both:
        notices.append(
            f"Tags both included and excluded: {', '.join(in_both)}. The excluded tags still apply: "
            "check the two lists."
        )

    included_tag_counts = {tag: count_datasets_with_tag(project_datasets, tag) for tag in selection.included_tags}
    excluded_tag_counts = {tag: count_datasets_with_tag(project_datasets, tag) for tag in selection.excluded_tags}

    rows = [
        decide(tagged, selection, options, shared_datasets, datasets_without_recipe)
        for tagged in select_datasets(project_datasets, selection)
    ]
    rows.sort(key=lambda row: row["name"])

    for row in rows:
        logger.info("Decision for %s", describe_row(row))
    for notice in notices:
        logger.warning(notice)
    for blocker in blockers:
        logger.warning("A real run stops here: %s", blocker)

    if blockers and not simulate:
        raise RunStopped("Nothing was cleared. " + " ".join(blockers))

    # Step 2: clear the datasets, one after the other. With "Raise exception", the first failure
    # stops the clearing: the datasets after it are not tried, and the runner ends the run in error.
    stopped = False
    for position, row in enumerate(rows, start=1):
        if row["status"] == STATUS_WOULD_BE_CLEARED and not simulate:
            if stopped:
                row.update(status=STATUS_SKIPPED, skip_code=SKIP_STOPPED, detail="Not tried: the run stopped")
            else:
                row["status"], detail, row["duration"] = clear_dataset(project, row["name"])
                # A message from DSS or an error says more than why the dataset was selected.
                row["detail"] = detail or row["detail"]
                logger.info("[%d/%d] %s, in %.2f s", position, len(rows), describe_row(row), row["duration"])
                if row["status"] == STATUS_FAILED and options["on_error"] == ON_ERROR_STOP:
                    stopped = True
                    logger.error("The run stops at the first error, as 'If an error occurs' asks")
        progress_callback(position * 100 // len(rows))

    if not rows:
        progress_callback(100)

    return {
        "simulate": simulate,
        "options": options,
        "included_tags": selection.included_tags,
        "included_match": selection.included_match,
        "excluded_tags": selection.excluded_tags,
        "excluded_match": selection.excluded_match,
        "included_tag_counts": included_tag_counts,
        "excluded_tag_counts": excluded_tag_counts,
        "sharing_checked": shared_datasets is not None,
        "recipes_checked": datasets_without_recipe is not None,
        "notices": notices,
        "blockers": blockers,
        "scanned_count": len(project_datasets),
        "datasets": rows,
    }
