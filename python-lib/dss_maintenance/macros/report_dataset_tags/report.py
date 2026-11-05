"""Report how the datasets of a project use tags. It only reads: nothing is changed.

Each tag gets a status:

- Used: at least one dataset has it.
- Unknown: a dataset has it, but it looks like a category tag ("category:value") and the global tag
  categories of the instance have no such category or value. Maybe a typo.
- Unused: it is in the project tag list, but no dataset has it. The project tag list also holds
  the tags of other objects, such as recipes or notebooks.

The datasets with no tag get their own row, with the status Untagged.
"""

import logging
from collections.abc import Callable
from typing import Any, Optional

from dss_maintenance.core.options import read_checkbox, read_recap_options
from dss_maintenance.core.project import list_project_datasets
from dss_maintenance.core.tags import split_category_tag

logger = logging.getLogger(__name__)

STATUS_UNKNOWN = "UNKNOWN"
STATUS_UNTAGGED = "UNTAGGED"
STATUS_UNUSED = "UNUSED"
STATUS_USED = "USED"
STATUS_LABELS = {
    STATUS_UNKNOWN: "Unknown",
    STATUS_UNTAGGED: "Untagged",
    STATUS_UNUSED: "Unused",
    STATUS_USED: "Used",
}

# Default value and label of the options of this macro, as in its form. A test checks that the form
# agrees. The options of the "Summary" section are in core/options.py. A report changes nothing, so
# it has no "Run" section: only "If the summary is not written" can fail the run.
OPTION_DEFAULTS = {"show_unused_tags": True, "aggregate_by_tag": True}
OPTION_LABELS = {"show_unused_tags": "Show unused tags", "aggregate_by_tag": "Aggregate by tag"}


def read_options(config: dict[str, Any], project_key: str) -> dict[str, Any]:
    """Return the options of the form. An "on_error" sent through the API is ignored."""
    options = {name: read_checkbox(config, name, default) for name, default in OPTION_DEFAULTS.items()}
    options.update(read_recap_options(config, project_key))
    return options


def read_project_tags(project: Any) -> list[str]:
    """Return the project tag list. DSS adds a tag to it when an object of the project gets it."""
    return sorted(str(tag) for tag in project.get_tags().get("tags") or {})


def read_tag_categories(project: Any) -> dict[str, set[str]]:
    """Return the global tag categories of the instance, with their tags.

    They are in the general settings, which only DSS administrators can read: for other users, this raises.
    """
    settings = project.client.get_general_settings().get_raw()
    return {
        str(category.get("name") or ""): {str(tag.get("name") or "") for tag in category.get("globalTags") or []}
        for category in settings.get("globalTagsCategories") or []
    }


def check_category_tag(tag: str, categories: dict[str, set[str]]) -> str:
    """Return why a category tag is unknown, or "" when it is known. A tag without a category is never unknown."""
    category, value = split_category_tag(tag)
    if not category:
        return ""
    if category not in categories:
        return f"No tag category {category}"
    if value not in categories[category]:
        return f"Category {category} has no tag {value}"
    return ""


def make_tag_row(tag: str, status: str, detail: str, datasets: list[str]) -> dict[str, Any]:
    """Return the row of one tag in the report."""
    return {
        "tag": tag,
        "category": split_category_tag(tag)[0],
        "status": status,
        "detail": detail,
        "datasets": datasets,
    }


def run_report(
    project: Any, project_key: str, config: dict[str, Any], progress_callback: Callable[[int], None]
) -> dict[str, Any]:
    """Read the tags of the datasets and return what the recap needs.

    :param project: project handle from dataiku.api_client()
    :param project_key: key of this project
    :param config: values of the macro form
    :param progress_callback: called with 100 at the end
    :raises ValueError: if the form is not valid
    """
    options = read_options(config, project_key)
    logger.info("Options: %s", options)
    notices: list[str] = []  # What the reader must know. The report is still made.

    datasets = sorted(list_project_datasets(project, project_key), key=lambda dataset: dataset["name"])

    categories: Optional[dict[str, set[str]]] = None
    try:
        categories = read_tag_categories(project)
    except Exception as error:
        notices.append(
            f"Category tags not checked: DSS did not give the tag categories ({error}). "
            "Only DSS administrators can read them."
        )

    project_tags: list[str] = []
    if options["show_unused_tags"]:
        try:
            project_tags = read_project_tags(project)
        except Exception as error:
            notices.append(f"Unused tags not listed: reading the project tag list failed ({error}).")

    datasets_by_tag: dict[str, list[str]] = {}
    untagged_datasets = []
    for dataset in datasets:
        tags = list(dict.fromkeys(str(tag) for tag in dataset.get("tags") or []))
        if not tags:
            untagged_datasets.append(dataset["name"])
        for tag in tags:
            datasets_by_tag.setdefault(tag, []).append(dataset["name"])

    rows = []
    for tag, names in datasets_by_tag.items():
        detail = "" if categories is None else check_category_tag(tag, categories)
        rows.append(make_tag_row(tag, STATUS_UNKNOWN if detail else STATUS_USED, detail, names))
    for tag in project_tags:
        if tag not in datasets_by_tag:
            rows.append(make_tag_row(tag, STATUS_UNUSED, "In the project tag list, on no dataset", []))
    rows.sort(key=lambda row: (row["tag"].lower(), row["tag"]))

    for row in rows:
        detail = f" - {row['detail']}" if row["detail"] else ""
        logger.info(
            "Tag %s: %s, on %d datasets%s", row["tag"], STATUS_LABELS[row["status"]], len(row["datasets"]), detail
        )
    logger.info("Datasets with no tag: %s", ", ".join(untagged_datasets) or "none")
    for notice in notices:
        logger.warning(notice)
    progress_callback(100)

    return {
        "options": options,
        "notices": notices,
        "blockers": [],
        "categories_checked": categories is not None,
        "known_categories": None if categories is None else sorted(categories),
        "scanned_count": len(datasets),
        "dataset_types": {dataset["name"]: dataset.get("type") or "" for dataset in datasets},
        "tags": rows,
        "untagged_datasets": untagged_datasets,
    }
