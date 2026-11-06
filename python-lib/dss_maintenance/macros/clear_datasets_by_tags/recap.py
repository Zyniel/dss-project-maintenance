"""What the recap of "Clear Datasets by Tags" holds: the JSON summary, the recap dataset, the HTML page."""

from typing import Any

from dss_maintenance.core.tags import SCOPE_ALL_DATASETS, SCOPE_LABEL
from dss_maintenance.macros.clear_datasets_by_tags.cleanup import (
    OPTION_LABELS,
    SKIP_STOPPED,
    STATUS_CLEARED,
    STATUS_EXCLUDED,
    STATUS_FAILED,
    STATUS_LABELS,
    STATUS_SKIPPED,
    STATUS_WOULD_BE_CLEARED,
    count_by_status,
)
from dss_maintenance.recap.dataset import format_flag
from dss_maintenance.recap.html import build_common_option_chips, count_of, format_duration, yes_no
from dss_maintenance.recap.page import (
    ALL_STATUSES,
    COLUMN_LONG_TEXT,
    COLUMN_NUMBER,
    COLUMN_STATUS,
    COLUMN_TAGS,
    ICON_CHECK,
    ICON_CLOCK,
    ICON_CROSS,
    ICON_MINUS,
    ICON_WARNING,
    TONE_CAUTION,
    TONE_DANGER,
    TONE_MUTED,
    TONE_PENDING,
    TONE_SUCCESS,
    Banner,
    Chip,
    Column,
    Metric,
    RecapPage,
    Section,
    Status,
    Table,
)

# Every column is stored as text: see write_recap_dataset().
RECAP_COLUMNS = [
    "run_id",
    "run_started_at",
    "macro",
    "project_key",
    "run_by",
    "simulate",
    "dataset",
    "dataset_type",
    "status",
    "skip_code",
    "detail",
    "warnings",
    "included_tags",
    "excluded_tags",
    "is_shared",
    "shared_with",
    "built_by_recipe",
    "partition_dimensions",
    "clear_duration_seconds",
]

# Failed dataset names given in the failure message. The recap has all of them.
FAILED_NAMES_SHOWN = 10

# The statuses of the table, failures first.
STATUSES = [
    Status(STATUS_FAILED, STATUS_LABELS[STATUS_FAILED], TONE_DANGER, ICON_CROSS),
    Status(STATUS_CLEARED, STATUS_LABELS[STATUS_CLEARED], TONE_SUCCESS, ICON_CHECK),
    Status(STATUS_WOULD_BE_CLEARED, STATUS_LABELS[STATUS_WOULD_BE_CLEARED], TONE_PENDING, ICON_CLOCK),
    Status(STATUS_SKIPPED, STATUS_LABELS[STATUS_SKIPPED], TONE_CAUTION, ICON_WARNING),
    Status(STATUS_EXCLUDED, STATUS_LABELS[STATUS_EXCLUDED], TONE_MUTED, ICON_MINUS),
]

COLUMNS = [
    Column("dataset", "Dataset", width=180, pinned=True),
    Column("status", "Status", COLUMN_STATUS, width=150),
    Column("detail", "Detail", COLUMN_LONG_TEXT, width=220, fill=True),
    Column("included_tags", "Included tags", COLUMN_TAGS, width=220),
    Column("excluded_tags", "Excluded tags", COLUMN_TAGS, width=170),
    Column("type", "Type", width=110),
    Column("duration", "Duration (s)", COLUMN_NUMBER, width=110),
]

# The options of this macro shown in the recap, in the order of the form. Simulate has its banner.
SHOWN_OPTIONS = ["purge_shared", "purge_partitioned", "purge_without_recipe"]


def round_duration(duration: Any) -> Any:
    """Return a duration in seconds rounded to the millisecond, or None when nothing was cleared."""
    return None if duration is None else round(duration, 3)


def describe_counts(recap: dict[str, Any]) -> str:
    """Return the totals of the run for the log, for the statuses this kind of run can have."""
    counts = count_by_status(recap["datasets"])
    # A simulation clears nothing, so nothing fails. A real run marks nothing "Cleared (Simulate)".
    other_mode = {STATUS_CLEARED, STATUS_FAILED} if recap["simulate"] else {STATUS_WOULD_BE_CLEARED}
    totals = ", ".join(
        f"{count} {STATUS_LABELS[status].lower()}" for status, count in counts.items() if status not in other_mode
    )
    return f"{totals}, out of {len(recap['datasets'])} selected and {recap['scanned_count']} scanned datasets"


def build_summary(recap: dict[str, Any]) -> dict[str, Any]:
    """Return the recap as plain JSON data: for the API, the run log and the hidden block of the HTML."""
    counts = count_by_status(recap["datasets"])
    return {
        "run_id": recap["run_id"],
        "macro": recap["macro"],
        "project_key": recap["project_key"],
        "run_by": recap["run_by"],
        "started_at": recap["started_at"],
        "simulate": recap["simulate"],
        "options": recap["options"],
        "included_scope": recap["included_scope"],
        "included_tags": recap["included_tags"],
        "included_match": recap["included_match"],
        "excluded_tags": recap["excluded_tags"],
        "excluded_match": recap["excluded_match"],
        "included_tag_counts": recap["included_tag_counts"],
        "excluded_tag_counts": recap["excluded_tag_counts"],
        "sharing_checked": recap["sharing_checked"],
        "recipes_checked": recap["recipes_checked"],
        "notices": recap["notices"],
        "blockers": recap["blockers"],
        "counts": {
            "scanned": recap["scanned_count"],
            "selected": len(recap["datasets"]),
            "cleared": counts[STATUS_CLEARED],
            "would_be_cleared": counts[STATUS_WOULD_BE_CLEARED],
            "failed": counts[STATUS_FAILED],
            "skipped": counts[STATUS_SKIPPED],
            "excluded": counts[STATUS_EXCLUDED],
        },
        "duration_seconds": round(recap["duration"], 3),
        "recap_dataset": recap["recap_dataset_result"],
        "datasets": [
            {
                "name": row["name"],
                "type": row["type"],
                "connection": row["connection"],
                "status": row["status"],
                "skip_code": row["skip_code"],
                "detail": row["detail"],
                "warnings": row["warnings"],
                "included_tags": row["included_tags"],
                "excluded_tags": row["excluded_tags"],
                "is_shared": row["is_shared"],
                "shared_with": row["shared_with"],
                "built_by_recipe": row["built_by_recipe"],
                "partition_dimensions": row["partition_dimensions"],
                "duration_seconds": round_duration(row["duration"]),
            }
            for row in recap["datasets"]
        ],
    }


def build_recap_rows(recap: dict[str, Any]) -> list[list[str]]:
    """Return one row per selected dataset, in the order of RECAP_COLUMNS."""
    rows = []
    for row in recap["datasets"]:
        shared_with = ""
        if row["is_shared"]:
            shared_with = ", ".join(row["shared_with"]) or "other projects"
        duration = "" if row["duration"] is None else f"{row['duration']:.3f}"
        rows.append(
            [
                recap["run_id"],
                recap["started_at"],
                recap["macro"],
                recap["project_key"],
                recap["run_by"],
                format_flag(recap["simulate"]),
                row["name"],
                row["type"],
                row["status"],
                row["skip_code"],
                row["detail"],
                " | ".join(row["warnings"]),
                ", ".join(row["included_tags"]),
                ", ".join(row["excluded_tags"]),
                format_flag(row["is_shared"]),
                shared_with,
                format_flag(row["built_by_recipe"]),
                ", ".join(row["partition_dimensions"]),
                duration,
            ]
        )
    return rows


def describe_failures(recap: dict[str, Any]) -> str:
    """Return the datasets that could not be cleared, or "". The runner decides if the run fails."""
    failed_names = [row["name"] for row in recap["datasets"] if row["status"] == STATUS_FAILED]
    if not failed_names:
        return ""

    cleared_count = count_by_status(recap["datasets"])[STATUS_CLEARED]
    names = ", ".join(failed_names[:FAILED_NAMES_SHOWN])
    if len(failed_names) > FAILED_NAMES_SHOWN:
        names += f" and {len(failed_names) - FAILED_NAMES_SHOWN} more"
    to_clear = count_of(len(failed_names) + cleared_count, "dataset")
    message = f"{len(failed_names)} of {to_clear} to clear failed: {names}."
    if cleared_count == 1:
        message += " The other one was cleared."
    elif cleared_count:
        message += f" The other {cleared_count} were cleared."
    not_tried = sum(1 for row in recap["datasets"] if row["skip_code"] == SKIP_STOPPED)
    if not_tried:
        verb = "was" if not_tried == 1 else "were"
        message += f" The run stopped at the first error: {count_of(not_tried, 'dataset')} {verb} not tried."
    return message


def build_banners(recap: dict[str, Any]) -> list[Banner]:
    """Return the banners of this macro. The shared code adds the notices and the recap dataset result."""
    banners = []
    if recap["simulate"]:
        banners.append(
            Banner(
                TONE_CAUTION,
                "Simulation: nothing was cleared.",
                'Uncheck "Simulate" and run the macro again to clear the datasets marked '
                f'"{STATUS_LABELS[STATUS_WOULD_BE_CLEARED]}".',
            )
        )
    if recap["blockers"]:
        banners.append(
            Banner(TONE_DANGER, "A real run would stop before clearing anything:", items=tuple(recap["blockers"]))
        )
    return banners


def build_metrics(recap: dict[str, Any]) -> list[Metric]:
    """Return the headline figures of the run."""
    counts = count_by_status(recap["datasets"])

    def status_metric(status: str, tone: str = "") -> Metric:
        # Clicking the figure shows the datasets of this status: it has the label of the table.
        return Metric(STATUS_LABELS[status], str(counts[status]), tone, status)

    metrics = []
    if recap["simulate"]:
        metrics.append(status_metric(STATUS_WOULD_BE_CLEARED))
    else:
        metrics.append(status_metric(STATUS_CLEARED, TONE_SUCCESS))
        metrics.append(status_metric(STATUS_FAILED, TONE_DANGER))
    metrics.append(status_metric(STATUS_SKIPPED))
    if recap["excluded_tags"]:
        metrics.append(status_metric(STATUS_EXCLUDED, TONE_MUTED))
    metrics.append(Metric("Selected", str(len(recap["datasets"])), status=ALL_STATUSES))
    metrics.append(Metric("Scanned", str(recap["scanned_count"])))
    metrics.append(Metric("Duration", format_duration(recap["duration"])))
    return metrics


def build_tag_section(title: str, match: str, tag_counts: dict[str, int], highlight_unmatched: bool) -> Section:
    """Return a list of tags with how it matches and the number of datasets carrying each tag."""
    chips = tuple(
        Chip(f"{tag} ({count})", TONE_CAUTION if highlight_unmatched and not count else "")
        for tag, count in tag_counts.items()
    )
    return Section(title, f"(Matching {match.title()})", chips)


def build_sections(recap: dict[str, Any]) -> list[Section]:
    """Return the options of the run, then the included and excluded tags."""
    options = recap["options"]
    option_chips = [Chip(f"{OPTION_LABELS[option]}: {yes_no(options[option])}") for option in SHOWN_OPTIONS]
    sections = [Section("Options", chips=tuple(option_chips + build_common_option_chips(options)))]

    if recap["included_scope"] == SCOPE_ALL_DATASETS:
        sections.append(Section(SCOPE_LABEL, text="All datasets of the project."))
    else:
        # An included tag on no dataset selects nothing: it stands out, it may be a typo.
        sections.append(build_tag_section("Included tags", recap["included_match"], recap["included_tag_counts"], True))
    if recap["excluded_tags"]:
        sections.append(
            build_tag_section("Excluded tags", recap["excluded_match"], recap["excluded_tag_counts"], False)
        )
    return sections


def build_table(recap: dict[str, Any]) -> Table:
    """Return the table of the selected datasets."""
    rows = [
        {
            "dataset": row["name"],
            "status": row["status"],
            "detail": "; ".join(part for part in [row["detail"], *row["warnings"]] if part),
            "included_tags": row["included_tags"],
            "excluded_tags": row["excluded_tags"],
            "type": row["type"],
            "duration": round_duration(row["duration"]),
        }
        for row in recap["datasets"]
    ]
    if recap["included_scope"] == SCOPE_ALL_DATASETS:
        empty_message = "This project has no dataset."
    else:
        empty_message = "No dataset of this project matches the included tags."
    return Table(
        title="Selected datasets",
        columns=COLUMNS,
        statuses=STATUSES,
        rows=rows,
        empty_message=empty_message,
        search_placeholder="Search datasets, tags, details",
        csv_file_name="clear-datasets-by-tags-recap.csv",
    )


def build_recap_page(recap: dict[str, Any]) -> RecapPage:
    """Return what the HTML recap shows."""
    return RecapPage(
        banners=build_banners(recap),
        metrics=build_metrics(recap),
        sections=build_sections(recap),
        table=build_table(recap),
        summary=build_summary(recap),
    )
