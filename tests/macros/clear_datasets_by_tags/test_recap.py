"""Tests of the recap: the JSON summary, the recap dataset rows, the failure message and the HTML page."""

import json
import re
from typing import Any

from dss_project_maintenance.macros.clear_datasets_by_tags import MACRO
from dss_project_maintenance.macros.clear_datasets_by_tags.cleanup import (
    STATUS_CLEARED,
    STATUS_EXCLUDED,
    STATUS_FAILED,
    STATUS_SKIPPED,
    STATUS_WOULD_BE_CLEARED,
)
from dss_project_maintenance.macros.clear_datasets_by_tags.recap import (
    COLUMNS,
    RECAP_COLUMNS,
    STATUSES,
    build_recap_page,
    build_recap_rows,
    build_summary,
    describe_counts,
    describe_failures,
)
from dss_project_maintenance.recap.html import build_recap_html
from support.fakes import FakeProject, make_dataset
from support.runs import run

REAL_RUN = {"simulate": False}


def make_row(name: str, status: str, **values: Any) -> dict[str, Any]:
    row = {
        "name": name,
        "type": "Oracle",
        "connection": "ora",
        "included_tags": ["a"],
        "excluded_tags": [],
        "is_shared": False,
        "shared_with": [],
        "built_by_recipe": True,
        "partition_dimensions": [],
        "status": status,
        "skip_code": "",
        "detail": "",
        "warnings": [],
        "duration": 1.23456,
    }
    row.update(values)
    return row


def make_recap(rows: list[dict[str, Any]], **values: Any) -> dict[str, Any]:
    recap = {
        "run_id": "r1",
        "macro": MACRO.id,
        "macro_label": MACRO.label,
        "project_key": "TEST",
        "run_by": "jdoe",
        "started_at": "2026-11-02T19:10:00Z",
        "simulate": False,
        "options": {},
        "included_scope": "TAGS",
        "included_tags": ["a"],
        "included_match": "ANY",
        "excluded_tags": [],
        "excluded_match": "ANY",
        "included_tag_counts": {"a": 1},
        "excluded_tag_counts": {},
        "sharing_checked": True,
        "recipes_checked": True,
        "notices": [],
        "blockers": [],
        "scanned_count": 10,
        "datasets": rows,
        "duration": 90.0,
        "recap_dataset_result": None,
    }
    recap.update(values)
    return recap


def recap_html(project: FakeProject, config: dict[str, Any]) -> str:
    recap, _ = run(MACRO, project, config)
    return build_recap_html(recap, build_recap_page(recap))


def metric(html: str, label: str) -> str:
    """Return the value displayed above a metric label."""
    before_label = html[: html.index(f'<span class="dtp-metric-label">{label}<')]
    value_start = before_label.rindex('">') + 2
    return before_label[value_start:].replace("</span>", "")


# JSON summary and log


def test_summary_of_a_real_run_is_plain_json() -> None:
    project = FakeProject([make_dataset("ok", ["a"]), make_dataset("ext", ["a"], managed=False)], shared={"ok": ["B"]})
    recap, _ = run(MACRO, project, {"included_tags": ["a"], "purge_shared": True, **REAL_RUN})

    summary = json.loads(json.dumps(build_summary(recap)))

    assert summary["counts"] == {
        "scanned": 2,
        "selected": 2,
        "cleared": 1,
        "would_be_cleared": 0,
        "failed": 0,
        "skipped": 1,
        "excluded": 0,
    }
    assert summary["macro"] == "clear-datasets-by-tags"
    assert summary["run_by"] == "jdoe"
    assert summary["options"]["simulate"] is False
    assert (summary["included_scope"], summary["included_tags"]) == ("TAGS", ["a"])
    ok = summary["datasets"][1]
    assert (ok["name"], ok["status"], ok["shared_with"]) == ("ok", STATUS_CLEARED, ["B"])
    assert summary["datasets"][0]["skip_code"] == "EXTERNAL"


def test_summary_gives_the_notices_and_the_blockers_as_texts() -> None:
    project = FakeProject([make_dataset("ds", ["a"])], is_admin=False, flow_error=RuntimeError("timeout"))
    config = {"included_tags": ["a"], "purge_shared": False, "purge_without_recipe": True}
    recap, _ = run(MACRO, project, config)

    summary = json.loads(json.dumps(build_summary(recap)))

    assert summary["notices"] == ["Recipes not checked. Datasets with no recipe are cleared too. DSS said: timeout."]
    assert summary["blockers"] == [
        'Sharing not checked. Check "Clear shared datasets", or ask a project administrator to run the macro. '
        "DSS said: Action forbidden, you are not admin of this project."
    ]


def test_describe_counts_for_the_log() -> None:
    recap = make_recap([make_row("ok", STATUS_CLEARED), make_row("ko", STATUS_FAILED)])

    assert describe_counts(recap) == (
        "1 cleared, 1 failed, 0 skipped, 0 excluded, out of 2 selected and 10 scanned datasets"
    )


def test_describe_counts_of_a_simulation_has_only_its_statuses() -> None:
    recap = make_recap([make_row("ds", STATUS_WOULD_BE_CLEARED), make_row("ext", STATUS_SKIPPED)], simulate=True)

    assert describe_counts(recap) == (
        "1 cleared (simulate), 1 skipped, 0 excluded, out of 2 selected and 10 scanned datasets"
    )


# Summary dataset


def test_one_recap_row_per_selected_dataset_in_the_column_order() -> None:
    recap = make_recap(
        [
            make_row("ok", STATUS_CLEARED, is_shared=True, shared_with=["B", "C"], warnings=["w1", "w2"]),
            make_row("unknown", STATUS_SKIPPED, is_shared=None, built_by_recipe=None, duration=None, skip_code="X"),
            make_row(
                "anon", STATUS_EXCLUDED, is_shared=True, shared_with=[], excluded_tags=["k1", "k2"], included_tags=[]
            ),
        ]
    )

    rows = build_recap_rows(recap)

    records = [dict(zip(RECAP_COLUMNS, row)) for row in rows]
    assert MACRO.recap_columns == RECAP_COLUMNS
    assert all(len(row) == len(RECAP_COLUMNS) for row in rows)
    assert records[0]["run_id"] == "r1"
    assert records[0]["simulate"] == "false"
    assert records[0]["shared_with"] == "B, C"
    assert records[0]["warnings"] == "w1 | w2"
    assert records[0]["clear_duration_seconds"] == "1.235"
    assert (records[1]["is_shared"], records[1]["built_by_recipe"]) == ("", "")
    assert records[1]["clear_duration_seconds"] == ""
    assert records[2]["shared_with"] == "other projects"
    assert records[2]["excluded_tags"] == "k1, k2"


# Failures


def test_no_failure_when_everything_worked() -> None:
    assert describe_failures(make_recap([make_row("ok", STATUS_CLEARED)])) == ""


def test_failures_count_the_datasets_to_clear_not_the_skipped_ones() -> None:
    recap = make_recap([make_row("ok", STATUS_CLEARED), make_row("ko", STATUS_FAILED), make_row("s", STATUS_SKIPPED)])

    assert describe_failures(recap) == "1 of 2 datasets failed, 1 cleared."


def test_failures_count_the_datasets_not_tried_after_a_stop() -> None:
    recap = make_recap(
        [
            make_row("ok", STATUS_CLEARED),
            make_row("ko", STATUS_FAILED),
            make_row("later1", STATUS_SKIPPED, skip_code="STOPPED"),
            make_row("later2", STATUS_SKIPPED, skip_code="STOPPED"),
        ]
    )

    assert describe_failures(recap) == "1 of 4 datasets failed, 1 cleared, 2 not tried."


def test_failures_leave_out_a_count_of_zero_and_use_the_singular_for_one() -> None:
    assert describe_failures(make_recap([make_row("ko", STATUS_FAILED)])) == "1 of 1 dataset failed."
    recap = make_recap([make_row("ko", STATUS_FAILED), make_row("later", STATUS_SKIPPED, skip_code="STOPPED")])
    assert describe_failures(recap) == "1 of 2 datasets failed, 1 not tried."


def test_failures_never_name_the_datasets_however_many_they_are() -> None:
    recap = make_recap([make_row(f"ko{index:03d}", STATUS_FAILED) for index in range(180)])

    assert describe_failures(recap) == "180 of 180 datasets failed."


# HTML page


def test_recap_gives_the_metrics_of_a_real_run() -> None:
    project = FakeProject(
        [
            make_dataset("ok1", ["a"]),
            make_dataset("ok2", ["a"]),
            make_dataset("ko", ["a"]),
            make_dataset("ext", ["a"], managed=False),
            make_dataset("other", ["b"]),
        ],
        clear_answers={"ko": RuntimeError("boom")},
    )

    html = recap_html(project, {"included_tags": ["a"], **REAL_RUN})

    assert metric(html, "Cleared") == "2"
    assert metric(html, "Failed") == "1"
    assert metric(html, "Skipped") == "1"
    assert metric(html, "Selected") == "4"
    assert metric(html, "Scanned") == "5"
    assert re.match(r"\d+\.\d\d s$", metric(html, "Duration"))
    assert 'dtp-metric-label">Excluded' not in html
    assert "Simulation, nothing was cleared" not in html


def test_a_run_that_goes_on_counts_the_failures_in_a_red_banner() -> None:
    project = FakeProject(
        [make_dataset(name, ["a"]) for name in ("ok1", "ok2", "ko1", "ko2")],
        clear_answers={"ko1": RuntimeError("boom"), "ko2": RuntimeError("boom")},
    )

    html = recap_html(project, {"included_tags": ["a"], "on_error": "CONTINUE", **REAL_RUN})

    assert (
        '<div class="dtp-banner dtp-banner-danger"><strong>2 of 4 datasets failed.</strong> '
        '2 cleared. Click "Failed" to list them.</div>'
    ) in html


def test_a_failure_banner_with_nothing_cleared_says_only_how_to_list_it() -> None:
    project = FakeProject([make_dataset("ko", ["a"])], clear_answers={"ko": RuntimeError("boom")})

    html = recap_html(project, {"included_tags": ["a"], "on_error": "CONTINUE", **REAL_RUN})

    assert '<strong>1 of 1 dataset failed.</strong> Click "Failed" to list it.</div>' in html


def test_a_simulation_says_nothing_was_cleared() -> None:
    html = recap_html(FakeProject([make_dataset("ds", ["a"])]), {"included_tags": ["a"]})

    assert (
        '<div class="dtp-banner dtp-banner-pending"><strong>Simulation, nothing was cleared.</strong> '
        'Uncheck "Simulate" to clear.</div>'
    ) in html
    assert metric(html, "Cleared (Simulate)") == "1"
    assert 'dtp-metric-label">Cleared<' not in html


def test_a_simulation_shows_the_same_label_in_the_table_and_the_grid() -> None:
    html = recap_html(FakeProject([make_dataset("ds", ["a"])]), {"included_tags": ["a"]})

    table = html[html.index("<table>") :]
    assert "Cleared (Simulate)</span></td>" in table
    # The cells, the filter and the CSV export of the grid all take the label from these statuses.
    found = re.search(r"var statuses = (.*);$", html, re.MULTILINE)
    assert found
    statuses = json.loads(found.group(1))
    assert statuses[STATUS_WOULD_BE_CLEARED]["label"] == "Cleared (Simulate)"
    assert statuses[STATUS_CLEARED]["label"] == "Cleared"


def test_a_simulation_shows_why_a_real_run_would_stop() -> None:
    project = FakeProject([make_dataset("ds", ["a"])], is_admin=False)

    html = recap_html(project, {"included_tags": ["a"], "purge_shared": False})

    assert (
        '<div class="dtp-banner dtp-banner-danger"><strong>A real run would stop: sharing not checked.</strong> '
        'Check "Clear shared datasets", or ask a project administrator to run the macro. DSS said: '
    ) in html


def test_a_simulation_gives_one_banner_per_reason_to_stop() -> None:
    project = FakeProject([make_dataset("ds", ["a"])], is_admin=False, flow_error=RuntimeError("timeout"))

    html = recap_html(project, {"included_tags": ["a"], "purge_shared": False})

    assert "<strong>A real run would stop: sharing not checked.</strong>" in html
    assert (
        "<strong>A real run would stop: recipes not checked.</strong> "
        'Check "Clear datasets with no recipe", or run the macro again. DSS said: timeout.</div>'
    ) in html


def test_a_simulation_counts_the_datasets_to_clear_that_carry_a_risk() -> None:
    project = FakeProject(
        [
            make_dataset("shared", ["a"]),
            make_dataset("partitioned", ["a"], partitioned=True),
            make_dataset("both", ["a"], partitioned=True),
            make_dataset("source", ["a"]),
            make_dataset("plain", ["a"]),
        ],
        shared={"shared": ["PROJ_B"], "both": ["PROJ_B"]},
        without_recipe=["source"],
    )
    config = {"included_tags": ["a"], "purge_partitioned": True, "purge_without_recipe": True}

    html = recap_html(project, config)

    # "both" counts in shared and in partitioned, but as one dataset.
    assert (
        '<div class="dtp-banner"><strong>4 datasets to clear carry a risk.</strong> '
        "2 shared, 2 partitioned, 1 with no recipe.</div>"
    ) in html


def test_a_real_run_counts_only_the_cleared_datasets_that_carry_a_risk() -> None:
    project = FakeProject(
        [make_dataset("shared", ["a"]), make_dataset("shared_ko", ["a"])],
        shared={"shared": ["PROJ_B"], "shared_ko": ["PROJ_B"]},
        clear_answers={"shared_ko": RuntimeError("boom")},
    )

    html = recap_html(project, {"included_tags": ["a"], "on_error": "CONTINUE", **REAL_RUN})

    assert '<div class="dtp-banner"><strong>1 cleared dataset carries a risk.</strong> 1 shared.</div>' in html


def test_a_skipped_dataset_carries_no_risk() -> None:
    project = FakeProject([make_dataset("ds", ["a"], partitioned=True)])

    html = recap_html(project, {"included_tags": ["a"]})

    assert "a risk." not in html


def test_excluded_datasets_are_counted_and_listed() -> None:
    project = FakeProject([make_dataset("gold", ["keep"]), make_dataset("tmp", [])])

    html = recap_html(project, {"included_scope": "ALL_DATASETS", "excluded_tags": ["keep"]})

    assert metric(html, "Excluded") == "1"
    assert '<span class="dtp-status"><svg class="dtp-muted"' in html
    assert "</svg>Excluded</span></td>" in html
    assert "All datasets of the project." in html
    assert "<h3>Included tags" not in html


def test_the_table_row_joins_the_detail_and_the_warnings() -> None:
    project = FakeProject(
        [make_dataset("ds", ["a"], partitioned=True)],
        clear_answers={"ds": {"messages": [{"severity": "WARNING", "message": "slow"}]}},
    )
    recap, _ = run(MACRO, project, {"included_tags": ["a"], "purge_partitioned": True, **REAL_RUN})

    row = build_recap_page(recap).table.rows[0]

    assert row["detail"] == "WARNING: slow; All partitions are cleared (partitioned by day, country)"
    assert (row["dataset"], row["status"], row["included_tags"], row["type"]) == ("ds", "CLEARED", ["a"], "PostgreSQL")
    assert row["duration"] >= 0


def test_the_table_does_not_repeat_on_each_row_that_the_sharing_was_not_checked() -> None:
    project = FakeProject([make_dataset("ds", ["a"])], is_admin=False)
    recap, _ = run(MACRO, project, {"included_tags": ["a"]})

    assert build_recap_page(recap).table.rows[0]["detail"] == "Has included tags"
    # The summary dataset and the JSON recap keep it: each of their rows stands alone.
    warning = "Sharing not checked: other projects may use it"
    assert dict(zip(RECAP_COLUMNS, build_recap_rows(recap)[0]))["warnings"] == warning
    assert build_summary(recap)["datasets"][0]["warnings"] == [warning]


def test_every_status_and_column_of_the_table_is_known() -> None:
    assert {status.code for status in STATUSES} == {"CLEARED", "WOULD_BE_CLEARED", "FAILED", "SKIPPED", "EXCLUDED"}
    assert STATUSES[0].code == STATUS_FAILED  # Failures first.
    recap, _ = run(MACRO, FakeProject([make_dataset("ds", ["a"])]), {"included_tags": ["a"]})
    assert set(build_recap_page(recap).table.rows[0]) == {column.field for column in COLUMNS}


def test_nothing_selected_shows_a_message() -> None:
    html = recap_html(FakeProject([make_dataset("ds", ["other"])]), {"included_tags": ["a"]})

    assert "No dataset of this project matches the included tags." in html
    assert "<table>" not in html
    assert (
        '<div class="dtp-banner"><strong>No dataset selected.</strong> Included tags on no dataset: a.</div>'
    ) in html


def test_all_datasets_in_an_empty_project_shows_a_message() -> None:
    html = recap_html(FakeProject([]), {"included_scope": "ALL_DATASETS"})

    assert "This project has no dataset." in html


def test_an_included_tag_on_no_dataset_stands_out_and_the_match_is_shown() -> None:
    project = FakeProject([make_dataset("ds", ["a", "keep"])])
    config = {"included_tags": ["a", "typo"], "excluded_tags": ["keep", "NoInList"], "excluded_match": "ALL"}

    html = recap_html(project, config)

    assert '<h3>Included tags <span class="dtp-note">(Matching Any)</span></h3>' in html
    assert '<h3>Excluded tags <span class="dtp-note">(Matching All)</span></h3>' in html
    assert '<span class="dtp-tag">a (1)</span>' in html
    assert '<span class="dtp-tag dtp-tag-caution">typo (0)</span>' in html
    assert '<span class="dtp-tag">keep (1)</span>' in html
    assert '<span class="dtp-tag">NoInList (0)</span>' in html
    assert "<strong>2 tags are on no dataset.</strong> Included: typo. Excluded: NoInList.</div>" in html
    assert "would stop" not in html


def test_notices_and_options_are_shown() -> None:
    project = FakeProject([make_dataset("ds", ["a"])], is_admin=False)
    config = {"included_tags": ["a"], "purge_shared": True, "recap_dataset": "recap"}

    html = recap_html(project, config)

    assert '<div class="dtp-banner"><strong>Sharing not checked.</strong> ' in html
    assert '<span class="dtp-tag">Clear partitioned datasets: no</span>' in html
    assert '<span class="dtp-tag">Clear shared datasets: yes</span>' in html
    assert '<span class="dtp-tag">If an error occurs: Continue, run ends in error</span>' in html
    assert '<span class="dtp-tag">If the summary is not written: Continue</span>' in html
    assert '<span class="dtp-tag">Summary dataset: recap, earlier runs kept</span>' in html


def test_the_hidden_json_block_holds_the_summary() -> None:
    recap, _ = run(MACRO, FakeProject([make_dataset("ds", ["a"])]), {"included_tags": ["a"]})

    html = build_recap_html(recap, build_recap_page(recap))

    match = re.search(r'<script type="application/json" id="dtp-recap-data">(.*?)</script>', html, re.DOTALL)
    assert match
    expected = {**build_summary(recap), "outcome": "SUCCESS", "problems": []}
    assert json.loads(match.group(1)) == json.loads(json.dumps(expected))


def test_free_text_of_the_project_is_escaped() -> None:
    attack = "<script>alert(1)</script>{{constructor}}"
    dataset = make_dataset(attack, [attack], managed=False)
    dataset["type"] = attack
    dataset["params"]["connection"] = attack
    recap, _ = run(MACRO, FakeProject([dataset]), {"included_tags": [attack]})

    html = build_recap_html(recap, build_recap_page(recap))

    assert "<script>alert(1)" not in html
    assert "alert" not in html[html.rindex("<script>") :]
