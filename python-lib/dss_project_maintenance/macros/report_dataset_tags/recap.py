"""What the recap of "Report Dataset Tags" holds: the JSON summary, the recap dataset, the HTML page."""

from typing import Any

from dss_project_maintenance.macros.report_dataset_tags.report import (
    OPTION_LABELS,
    STATUS_LABELS,
    STATUS_UNKNOWN,
    STATUS_UNTAGGED,
    STATUS_UNUSED,
    STATUS_USED,
)
from dss_project_maintenance.recap.html import build_common_option_chips, count_of, format_duration, yes_no
from dss_project_maintenance.recap.page import (
    ALL_STATUSES,
    COLUMN_LONG_TEXT,
    COLUMN_NUMBER,
    COLUMN_STATUS,
    ICON_CHECK,
    ICON_CIRCLE,
    ICON_CROSS,
    ICON_WARNING,
    TONE_CAUTION,
    TONE_DANGER,
    TONE_MUTED,
    TONE_SUCCESS,
    Chip,
    Column,
    Metric,
    RecapPage,
    Section,
    Status,
    Table,
)

# One row per tag and dataset. An unused tag has a row with no dataset, and a dataset with no tag
# has a row with no tag. Every column is stored as text: see write_recap_dataset().
RECAP_COLUMNS = [
    "run_id",
    "run_started_at",
    "macro",
    "project_key",
    "run_by",
    "tag",
    "tag_category",
    "tag_status",
    "dataset",
    "dataset_type",
]

# The rows of the datasets with no tag have an empty tag, so that no real tag can be taken for them.
NO_TAG = ""

# The statuses of the table, the ones to look at first.
STATUSES = [
    Status(STATUS_UNKNOWN, STATUS_LABELS[STATUS_UNKNOWN], TONE_DANGER, ICON_CROSS),
    Status(STATUS_UNTAGGED, STATUS_LABELS[STATUS_UNTAGGED], TONE_CAUTION, ICON_WARNING),
    Status(STATUS_UNUSED, STATUS_LABELS[STATUS_UNUSED], TONE_MUTED, ICON_CIRCLE),
    Status(STATUS_USED, STATUS_LABELS[STATUS_USED], TONE_SUCCESS, ICON_CHECK),
]

# "Aggregate by tag" checked: one row per tag, with its datasets.
COLUMNS_BY_TAG = [
    Column("tag", "Tag", width=200, pinned=True),
    Column("status", "Status", COLUMN_STATUS, width=120),
    Column("detail", "Detail", COLUMN_LONG_TEXT, width=200),
    Column("dataset_count", "Datasets", COLUMN_NUMBER, width=100),
    Column("datasets", "Dataset names", COLUMN_LONG_TEXT, width=280, fill=True),
    Column("category", "Category", width=140),
]

# "Aggregate by tag" unchecked: one row per tag and dataset, as in the recap dataset.
COLUMNS_BY_TAG_AND_DATASET = [
    Column("tag", "Tag", width=200, pinned=True),
    Column("status", "Status", COLUMN_STATUS, width=120),
    Column("dataset", "Dataset", width=200),
    Column("type", "Type", width=120),
    Column("category", "Category", width=140),
    Column("detail", "Detail", COLUMN_LONG_TEXT, width=220, fill=True),
]


def count(recap: dict[str, Any]) -> dict[str, int]:
    """Return the figures of the report."""
    statuses = [row["status"] for row in recap["tags"]]
    return {
        "datasets": recap["scanned_count"],
        "tagged": recap["scanned_count"] - len(recap["untagged_datasets"]),
        "untagged": len(recap["untagged_datasets"]),
        "tags": len(statuses),
        "used": statuses.count(STATUS_USED),
        "unknown": statuses.count(STATUS_UNKNOWN),
        "unused": statuses.count(STATUS_UNUSED),
    }


def describe_counts(recap: dict[str, Any]) -> str:
    """Return the figures of the report for the log."""
    counts = count(recap)
    return (
        f"{counts['datasets']} datasets, {counts['untagged']} with no tag; {counts['tags']} tags: "
        f"{counts['used']} used, {counts['unknown']} unknown, {counts['unused']} unused"
    )


def build_summary(recap: dict[str, Any]) -> dict[str, Any]:
    """Return the recap as plain JSON data: for the API, the run log and the hidden block of the HTML."""
    return {
        "run_id": recap["run_id"],
        "macro": recap["macro"],
        "project_key": recap["project_key"],
        "run_by": recap["run_by"],
        "started_at": recap["started_at"],
        "options": recap["options"],
        "categories_checked": recap["categories_checked"],
        "notices": [str(notice) for notice in recap["notices"]],
        "counts": count(recap),
        "duration_seconds": round(recap["duration"], 3),
        "recap_dataset": recap["recap_dataset_result"],
        "tags": [
            {
                "tag": row["tag"],
                "category": row["category"],
                "status": row["status"],
                "detail": row["detail"],
                "dataset_count": len(row["datasets"]),
                "datasets": row["datasets"],
            }
            for row in recap["tags"]
        ],
        "untagged_datasets": recap["untagged_datasets"],
    }


def build_recap_rows(recap: dict[str, Any]) -> list[list[str]]:
    """Return the rows of the recap dataset, in the order of RECAP_COLUMNS."""
    run = [recap["run_id"], recap["started_at"], recap["macro"], recap["project_key"], recap["run_by"]]
    types = recap["dataset_types"]
    rows = []
    for row in recap["tags"]:
        tag = [row["tag"], row["category"], row["status"]]
        for name in row["datasets"] or [""]:
            rows.append(run + tag + [name, types.get(name, "")])
    for name in recap["untagged_datasets"]:
        rows.append(run + ["", "", STATUS_UNTAGGED, name, types.get(name, "")])
    return rows


def describe_failures(recap: dict[str, Any]) -> str:
    """A report changes nothing, so nothing in its work can fail. Only the recap dataset can."""
    return ""


def build_metrics(recap: dict[str, Any]) -> list[Metric]:
    """Return the headline figures of the report."""
    counts = count(recap)
    metrics = [
        Metric("Datasets", str(counts["datasets"])),
        Metric("Tagged", str(counts["tagged"])),
        Metric("Untagged", str(counts["untagged"]), TONE_CAUTION if counts["untagged"] else "", STATUS_UNTAGGED),
        Metric("Tags", str(counts["tags"]), status=ALL_STATUSES),
        Metric("Used", str(counts["used"]), TONE_SUCCESS, STATUS_USED),
    ]
    if recap["categories_checked"]:
        metrics.append(Metric("Unknown", str(counts["unknown"]), TONE_DANGER, STATUS_UNKNOWN))
    if recap["options"]["show_unused_tags"]:
        metrics.append(Metric("Unused", str(counts["unused"]), TONE_MUTED, STATUS_UNUSED))
    metrics.append(Metric("Duration", format_duration(recap["duration"])))
    return metrics


def build_category_chips(recap: dict[str, Any]) -> tuple[Chip, ...]:
    """Return one chip per category on the datasets, with its tags and datasets. An unknown category stands out."""
    tags_by_category: dict[str, int] = {}
    datasets_by_category: dict[str, set[str]] = {}
    for row in recap["tags"]:
        if row["category"] and row["datasets"]:
            tags_by_category[row["category"]] = tags_by_category.get(row["category"], 0) + 1
            datasets_by_category.setdefault(row["category"], set()).update(row["datasets"])
    known = recap["known_categories"]  # None when the categories could not be read.
    return tuple(
        Chip(
            f"{category}: {count_of(tags_by_category[category], 'tag')}, "
            f"{count_of(len(datasets_by_category[category]), 'dataset')}",
            TONE_CAUTION if known is not None and category not in known else "",
        )
        for category in sorted(tags_by_category, key=str.lower)
    )


def build_sections(recap: dict[str, Any]) -> list[Section]:
    """Return the options of the run, then the tag categories on the datasets."""
    options = recap["options"]
    option_chips = [Chip(f"{label}: {yes_no(options[option])}") for option, label in OPTION_LABELS.items()]
    category_chips = build_category_chips(recap)
    return [
        Section("Options", chips=tuple(option_chips + build_common_option_chips(options))),
        Section(
            "Tag categories", chips=category_chips, text="" if category_chips else "No category tag on the datasets."
        ),
    ]


def build_rows_by_tag(recap: dict[str, Any]) -> list[dict[str, Any]]:
    """Return one row per tag, and one row with an empty tag for the datasets with no tag.

    Dataset names are plain text.
    """
    rows = [
        {
            "tag": row["tag"],
            "status": row["status"],
            "detail": row["detail"],
            "dataset_count": len(row["datasets"]),
            "datasets": ", ".join(row["datasets"]),
            "category": row["category"],
        }
        for row in recap["tags"]
    ]
    if recap["untagged_datasets"]:
        rows.append(
            {
                "tag": NO_TAG,
                "status": STATUS_UNTAGGED,
                "detail": "Datasets with no tag",
                "dataset_count": len(recap["untagged_datasets"]),
                "datasets": ", ".join(recap["untagged_datasets"]),
                "category": "",
            }
        )
    return rows


def build_rows_by_tag_and_dataset(recap: dict[str, Any]) -> list[dict[str, Any]]:
    """Return one row per tag and dataset. An unused tag has a row with no dataset, and a dataset with no tag
    has a row with no tag."""
    types = recap["dataset_types"]
    rows = [
        {
            "tag": row["tag"],
            "status": row["status"],
            "dataset": name,
            "type": types.get(name, ""),
            "category": row["category"],
            "detail": row["detail"],
        }
        for row in recap["tags"]
        for name in row["datasets"] or [""]
    ]
    rows += [
        {
            "tag": NO_TAG,
            "status": STATUS_UNTAGGED,
            "dataset": name,
            "type": types.get(name, ""),
            "category": "",
            "detail": "No tag",
        }
        for name in recap["untagged_datasets"]
    ]
    return rows


def build_table(recap: dict[str, Any]) -> Table:
    """Return the table, with one row per tag, or one row per tag and dataset."""
    if recap["options"]["aggregate_by_tag"]:
        title, columns, rows = "Tags", COLUMNS_BY_TAG, build_rows_by_tag(recap)
    else:
        title, columns, rows = "Tags and datasets", COLUMNS_BY_TAG_AND_DATASET, build_rows_by_tag_and_dataset(recap)
    return Table(
        title=title,
        columns=columns,
        statuses=STATUSES,
        rows=rows,
        empty_message="This project has no dataset and no tag.",
        search_placeholder="Search tags, datasets, details",
        csv_file_name="report-dataset-tags-recap.csv",
    )


def build_recap_page(recap: dict[str, Any]) -> RecapPage:
    """Return what the HTML recap shows."""
    return RecapPage(
        banners=[],
        metrics=build_metrics(recap),
        sections=build_sections(recap),
        table=build_table(recap),
        summary=build_summary(recap),
    )
