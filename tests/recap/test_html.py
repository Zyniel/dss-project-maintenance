"""Tests of the HTML recap, with a page made by hand: layout, escaping, the hidden JSON and the grid script."""

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from dss_maintenance.recap import page
from dss_maintenance.recap.html import (
    AG_GRID_DEFAULT_INTEGRITY,
    AG_GRID_DEFAULT_URL,
    ICON_SHAPES,
    STYLE,
    build_common_option_chips,
    build_recap_html,
    count_of,
    format_duration,
    read_grid_cdn,
    to_html_script_json,
)
from dss_maintenance.recap.page import (
    ALL_STATUSES,
    COLUMN_LONG_TEXT,
    COLUMN_NUMBER,
    COLUMN_STATUS,
    COLUMN_TAGS,
    TONE_CAUTION,
    TONE_DANGER,
    TONE_MUTED,
    TONE_SUCCESS,
    Banner,
    Chip,
    Column,
    Metric,
    RecapPage,
    Section,
    Table,
)
from support.sample_macro import STATUS_DONE, STATUS_FAILED, STATUSES

COLUMNS = [
    Column("name", "Dataset", pinned=True),
    Column("status", "Status", COLUMN_STATUS),
    Column("detail", "Detail", COLUMN_LONG_TEXT, fill=True),
    Column("tags", "Tags", COLUMN_TAGS),
    Column("type", "Type"),
    Column("seconds", "Duration (s)", COLUMN_NUMBER),
]


def make_row(name: str, status: str = STATUS_DONE, **values: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "name": name,
        "status": status,
        "detail": "",
        "tags": [],
        "type": "PostgreSQL",
        "seconds": None,
    }
    row.update(values)
    return row


def make_recap(**values: Any) -> dict[str, Any]:
    recap: dict[str, Any] = {
        "run_id": "r1",
        "macro_label": "Sample Macro",
        "project_key": "TEST",
        "run_by": "jdoe",
        "started_at": "2026-11-02T19:10:00Z",
        "notices": [],
        "recap_dataset_result": None,
        "problems": [],
        "outcome": "SUCCESS",
    }
    recap.update(values)
    return recap


def make_page(rows: Any = None, **values: Any) -> RecapPage:
    rows = [make_row("a_ok", seconds=0.123), make_row("z_ko", STATUS_FAILED)] if rows is None else rows
    table = Table("Datasets", COLUMNS, STATUSES, rows, "Nothing to show.", "Search datasets", "sample.csv")
    page = RecapPage([], [Metric("Selected", str(len(rows)), status=ALL_STATUSES)], [], table, {"datasets": rows})
    return page._replace(**values)


def html_of(page: RecapPage, **recap_values: Any) -> str:
    return build_recap_html(make_recap(**recap_values), page)


def grid_script_of(html: str) -> str:
    return html[html.rindex("<script>") + len("<script>") : html.rindex("</script>")]


def test_count_of() -> None:
    assert (count_of(0, "row"), count_of(1, "row"), count_of(2, "dataset")) == ("0 rows", "1 row", "2 datasets")


def test_format_duration() -> None:
    assert format_duration(0.421) == "0.42 s"
    assert format_duration(90) == "1.5 min"


# Layout


def test_the_context_says_which_macro_ran_who_ran_it_and_when() -> None:
    html = html_of(make_page())

    # No title of its own: DSS already shows "Result" above it.
    assert "<h2>" not in html
    assert 'ng-non-bindable><p class="dtp-context">' in html
    assert "Sample Macro · Project TEST · Run by jdoe · Started 2026-11-02 19:10:00 UTC" in html
    assert "Run by unknown user" in html_of(make_page(), run_by="")


def test_banners_by_tone_then_the_notices_of_the_run() -> None:
    banners = [
        Banner(TONE_CAUTION, "Simulation: nothing was done.", 'Uncheck "Simulate".'),
        Banner(TONE_DANGER, "A real run would stop:", items=("reason 1", "reason 2")),
    ]

    html = html_of(make_page(banners=banners), notices=["Sharing not checked.", "Recipes not checked."])

    assert '<div class="dtp-banner"><strong>Simulation: nothing was done.</strong> Uncheck "Simulate".</div>' in html
    assert (
        '<div class="dtp-banner dtp-banner-danger"><strong>A real run would stop:</strong>'
        "<ul><li>reason 1</li><li>reason 2</li></ul></div>"
    ) in html
    # One banner per notice, as text: a list with no title above it would be indented.
    assert (
        '<div class="dtp-banner">Sharing not checked.</div><div class="dtp-banner">Recipes not checked.</div>' in html
    )
    assert html.index("A real run would stop") < html.index("Sharing not checked.")


def test_the_recap_dataset_written_is_shown() -> None:
    written = {"name": "recap", "rows_written": 1, "error": ""}
    assert '<div class="dtp-banner dtp-banner-muted">Summary written to dataset recap: 1 row.</div>' in html_of(
        make_page(), recap_dataset_result=written
    )

    failed = {"name": "recap", "rows_written": 0, "error": "ValueError"}
    assert "Recap written" not in html_of(make_page(), recap_dataset_result=failed)  # The outcome banner says it.


def test_the_outcome_banner_comes_first_and_lists_the_problems() -> None:
    problems = [{"message": "Failed: <d2>.", "fail": False}]
    banners = [Banner(TONE_CAUTION, "Simulation: nothing was done.")]

    html = html_of(make_page(banners=banners), problems=problems, outcome="WARNING")

    warning = (
        '<div class="dtp-banner"><strong>Warning: the run went on after these errors:</strong>'
        "<ul><li>Failed: &lt;d2&gt;.</li></ul></div>"
    )
    assert warning in html
    assert html.index(warning) < html.index("Simulation: nothing was done.")

    html = html_of(make_page(), problems=problems, outcome="FAILED")
    assert '<div class="dtp-banner dtp-banner-danger"><strong>The run failed after these errors:</strong>' in html


def test_no_outcome_banner_when_nothing_went_wrong() -> None:
    html = html_of(make_page())

    assert "the run went on" not in html and "The run failed" not in html


def test_metrics_with_their_tone_and_status_filter() -> None:
    metrics = [Metric("Done", "2", TONE_SUCCESS, STATUS_DONE), Metric("Duration", "0.42 s")]

    html = html_of(make_page(metrics=metrics))

    assert (
        '<div class="dtp-metric" data-status="DONE"><span class="dtp-metric-value dtp-success">2</span>'
        '<span class="dtp-metric-label">Done</span></div>'
    ) in html
    assert '<div class="dtp-metric"><span class="dtp-metric-value">0.42 s</span>' in html


def test_sections_with_a_note_chips_and_text() -> None:
    sections = [
        Section("Included tags", "(Matching Any)", (Chip("a (1)"), Chip("typo (0)", TONE_CAUTION))),
        Section("Excluded tags", text="None."),
    ]

    html = html_of(make_page(sections=sections))

    # Only the title is in bold.
    assert '<h3>Included tags <span class="dtp-note">(Matching Any)</span></h3>' in html
    assert ".dtp-recap h3 .dtp-note { font-weight: 400; }" in STYLE
    assert '<span class="dtp-tag">a (1)</span><span class="dtp-tag dtp-tag-caution">typo (0)</span>' in html
    assert '<div class="dtp-section"><h3>Excluded tags</h3>None.</div>' in html


def test_the_common_options_of_every_form() -> None:
    options = {"on_error": "FAIL", "recap_dataset": "recap", "recap_append": False, "on_recap_error": "CONTINUE"}
    assert build_common_option_chips(options) == [
        Chip("If an error occurs: Continue, run ends in error"),
        Chip("Summary dataset: recap, replaced by this run"),
        Chip("If the summary is not written: Continue"),
    ]

    # No recap dataset: what to do if it is not written does not matter.
    options = {"on_error": "CONTINUE", "recap_dataset": None, "recap_append": True, "on_recap_error": "FAIL"}
    assert build_common_option_chips(options) == [
        Chip("If an error occurs: Continue, run ends as success"),
        Chip("Summary dataset: none"),
    ]

    # A form without the "Run" section, such as a report.
    options = {"recap_dataset": None, "recap_append": True, "on_recap_error": "CONTINUE"}
    assert build_common_option_chips(options) == [Chip("Summary dataset: none")]


def test_the_font_is_set_for_a_downloaded_recap_too() -> None:
    html = html_of(make_page())

    assert ".dtp-recap, .dtp-recap table {" in html
    assert '"Segoe UI", Roboto' in html
    assert "sans-serif;" in html


# The static table


def test_the_static_table_shows_each_kind_of_column() -> None:
    rows = [make_row("ds", detail="All partitions are cleared", tags=["a", "b"], seconds=1.5)]

    html = html_of(make_page(rows))

    assert '<th class="dtp-number">Duration (s)</th>' in html
    assert '<td class="dtp-wrap">ds</td>' in html  # Pinned: may wrap.
    assert '<span class="dtp-status"><svg class="dtp-success"' in html
    assert "</svg>Done</span></td>" in html
    assert '<td class="dtp-wrap">All partitions are cleared</td>' in html
    assert '<td><span class="dtp-tag">a</span><span class="dtp-tag">b</span></td>' in html
    assert "<td>PostgreSQL</td>" in html
    assert '<td class="dtp-nowrap dtp-number">1.5</td>' in html


def test_the_static_table_sorts_by_status_failures_first() -> None:
    html = html_of(make_page())

    table = html[html.index("<table>") :]
    assert table.index("z_ko") < table.index("a_ok")
    assert '<td class="dtp-nowrap dtp-number"></td>' in table  # No duration.


def test_a_status_the_table_does_not_list_shows_its_code_last() -> None:
    rows = [make_row("odd", "STRANGE"), make_row("ok"), make_row("ko", STATUS_FAILED)]

    html = html_of(make_page(rows))

    table = html[html.index("<table>") :]
    assert '<td><span class="dtp-status">STRANGE</span></td>' in table
    assert table.index("ko") < table.index("ok") < table.index("odd")


def test_the_grid_reads_every_status_through_a_fallback() -> None:
    script = grid_script_of(html_of(make_page()))

    # Only statusOf() reads the statuses: an unknown code never breaks the sort, the filter or the cells.
    assert script.count("statuses[") == 1
    assert 'return statuses[code] || {label: code == null ? "" : String(code), order: 1000, icon: ""};' in script


def test_without_rows_the_empty_message_replaces_the_table_and_the_grid() -> None:
    html = html_of(make_page([]))

    assert "<p>Nothing to show.</p>" in html
    assert "<table>" not in html
    assert "<script>" not in html


# Escaping


def test_free_text_is_escaped_and_angularjs_is_kept_out() -> None:
    attack = "<script>alert(1)</script>{{constructor}}"
    page = make_page(
        [make_row(attack, detail=attack, tags=[attack], type=attack)],
        banners=[Banner(TONE_MUTED, attack, attack, (attack,))],
        metrics=[Metric(attack, attack)],
        sections=[Section(attack, attack, (Chip(attack),), attack)],
        summary={"name": attack},
    )

    html = html_of(page, project_key=attack, run_by=attack, notices=[attack])

    assert "<script>alert(1)" not in html
    assert "&lt;script&gt;" in html
    root = '<div class="dtp-recap" id="dtp-recap-r1" ng-non-bindable>'
    assert root in html
    # Everything that could hold {{...}} is inside the element AngularJS leaves alone.
    assert html.index(root) < html.index("{{")
    assert html.rindex("{{") < html.index("</div><script>")
    # The grid script after it holds no data: it reads the escaped JSON block of the table.
    grid_script = grid_script_of(html)
    assert "alert" not in grid_script and "constructor" not in grid_script


def test_json_for_a_script_element_cannot_close_it_and_reads_back_the_same() -> None:
    data = {"name": "</script><script>alert(1)</script> & {{x}}"}

    json_text = to_html_script_json(data)

    assert "</script>" not in json_text
    assert "<" not in json_text and ">" not in json_text
    assert json.loads(json_text) == data


def test_the_hidden_json_blocks_hold_the_summary_and_the_rows() -> None:
    page = make_page()

    html = html_of(page)

    summary = re.search(r'<script type="application/json" id="dtp-recap-data">(.*?)</script>', html, re.DOTALL)
    rows = re.search(r'<script type="application/json" class="dtp-table-data">(.*?)</script>', html, re.DOTALL)
    assert summary and rows
    assert json.loads(summary.group(1)) == {**page.summary, "outcome": "SUCCESS", "problems": []}
    assert json.loads(rows.group(1)) == page.table.rows


# The interactive table


def test_the_grid_script_enhances_the_static_table_of_this_run() -> None:
    html = html_of(make_page())
    script = grid_script_of(html)

    assert 'document.getElementById("dtp-recap-r1")' in script
    assert '<div class="dtp-static-table"><table>' in html
    assert '<div class="dtp-metric" data-status="ALL">' in html
    assert '"FAILED": {"label": "Failed", "order": 0, "icon": "\\u003csvg class=\\"dtp-danger\\"' in script
    assert '{"field": "seconds", "header": "Duration (s)", "kind": "number", "width": 150' in script
    assert 'var texts = {"search": "Search datasets", "csvFileName": "sample.csv"};' in script
    # In DSS, its own AG Grid. Outside DSS, which always has AngularJS, the one of the settings.
    assert "if (usable(window.agGrid)) {" in script
    assert "} else if (!window.angular && cdn.url) {" in script
    # Without AG Grid, or if building the grid fails, the script leaves the static table.
    assert 'staticTable.style.display = ""' in script


def test_the_grid_uses_community_features_only() -> None:
    script = grid_script_of(html_of(make_page()))

    assert "agSetColumnFilter" not in script and "filter: true" not in script
    assert "suppressContextMenu: true" in script
    assert "exportDataAsExcel" not in script and "rowGroup" not in script


def test_the_grid_shows_icons_and_chips_but_exports_plain_values() -> None:
    script = grid_script_of(html_of(make_page()))

    assert "status.innerHTML = statusOf(params.value).icon" in script
    # The CSV export takes the label of the status and the tags as text, never the icons.
    assert "if (params.column.getColId() === statusField) { return statusOf(value).label; }" in script
    assert 'if (Array.isArray(value)) { return value.join(", "); }' in script
    assert 'text("span", "dtp-chip", tag)' in script
    # Numbers are right aligned with column settings of AG Grid, also in the flex cells of DSS: no grid CSS.
    assert 'def.type = "numericColumn";' in script
    assert 'def.cellStyle = {justifyContent: "flex-end"};' in script
    assert "ag-right-aligned" not in STYLE and "toFixed" not in script


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js checks the syntax of the grid script")
def test_the_grid_script_is_valid_javascript(tmp_path: Path) -> None:
    script = tmp_path / "grid.js"
    script.write_text(grid_script_of(html_of(make_page())), encoding="utf-8")

    subprocess.run(["node", "--check", str(script)], check=True, capture_output=True)


def test_each_icon_has_a_shape_and_no_tone_is_bold() -> None:
    icons = {value for name, value in vars(page).items() if name.startswith("ICON_")}
    assert icons == set(ICON_SHAPES)
    for tone in ["success", "danger", "muted", "pending", "caution"]:
        rule = STYLE[STYLE.index(f".dtp-recap .dtp-{tone} {{") :].split("}")[0]
        assert "font-weight" not in rule


# The AG Grid a recap opened outside DSS loads


def test_the_default_grid_cdn_is_the_ag_grid_dss_ships_with_its_hash() -> None:
    default = {"url": AG_GRID_DEFAULT_URL, "integrity": AG_GRID_DEFAULT_INTEGRITY}
    assert read_grid_cdn(None) == read_grid_cdn({}) == default
    assert "ag-grid-community@29.2.0" in AG_GRID_DEFAULT_URL


@pytest.mark.parametrize(
    ("settings", "expected"),
    [
        (
            {"ag_grid_url": "https://repo.example.com/ag-grid.js", "ag_grid_integrity": ""},
            {"url": "https://repo.example.com/ag-grid.js", "integrity": ""},
        ),
        (
            {"ag_grid_url": " https://repo.example.com/ag-grid.js ", "ag_grid_integrity": "sha384-abc+/="},
            {"url": "https://repo.example.com/ag-grid.js", "integrity": "sha384-abc+/="},
        ),
        ({"ag_grid_url": ""}, {"url": "", "integrity": ""}),
        ({"ag_grid_url": None}, {"url": "", "integrity": ""}),
        ({"ag_grid_url": "javascript:alert(1)"}, {"url": "", "integrity": ""}),
        ({"ag_grid_url": "/plugins/ag-grid.js"}, {"url": "", "integrity": ""}),
        ({"ag_grid_integrity": "md5-abc"}, {"url": "", "integrity": ""}),
        ({"ag_grid_integrity": "sha256-abc sha1-def"}, {"url": "", "integrity": ""}),
        # Several hashes, and options after "?", as the SRI standard allows.
        (
            {"ag_grid_url": "https://repo.example.com/ag.js", "ag_grid_integrity": "sha384-AAA sha512-BBB=="},
            {"url": "https://repo.example.com/ag.js", "integrity": "sha384-AAA sha512-BBB=="},
        ),
        (
            {"ag_grid_url": "https://repo.example.com/ag.js", "ag_grid_integrity": "sha256-abc?x"},
            {"url": "https://repo.example.com/ag.js", "integrity": "sha256-abc?x"},
        ),
    ],
)
def test_the_grid_cdn_of_the_plugin_settings(settings: dict[str, Any], expected: dict[str, str]) -> None:
    assert read_grid_cdn(settings) == expected


def test_the_grid_cdn_goes_into_the_script_without_closing_it() -> None:
    cdn = read_grid_cdn({"ag_grid_url": "https://repo.example.com/ag.js</script><script>alert(1)//"})

    html = build_recap_html(make_recap(), make_page(), cdn)

    assert html.count("</script>") == 3  # The two JSON blocks and the grid script.
    assert "https://repo.example.com/ag.js\\u003c/script\\u003e" in grid_script_of(html)


def test_no_grid_cdn_when_turned_off() -> None:
    script = grid_script_of(build_recap_html(make_recap(), make_page(), read_grid_cdn({"ag_grid_url": ""})))

    assert 'var cdn = {"url": "", "integrity": ""};' in script
    assert "cdn.jsdelivr.net" not in script
