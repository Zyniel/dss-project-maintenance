"""Build the HTML recap shown at the end of a macro run, from the RecapPage of the macro."""

import json
import logging
import re
from html import escape
from typing import Any, Optional

from dss_maintenance.core.options import (
    RECAP_ERROR_CHOICES,
    RECAP_OPTION_LABELS,
    RUN_ERROR_CHOICES,
    RUN_OPTION_LABELS,
)
from dss_maintenance.recap.page import (
    COLUMN_LONG_TEXT,
    COLUMN_NUMBER,
    COLUMN_STATUS,
    COLUMN_TAGS,
    ICON_CHECK,
    ICON_CIRCLE,
    ICON_CLOCK,
    ICON_CROSS,
    ICON_MINUS,
    ICON_WARNING,
    OUTCOME_FAILED,
    OUTCOME_WARNING,
    TONE_CAUTION,
    TONE_DANGER,
    TONE_MUTED,
    Banner,
    Chip,
    Column,
    Metric,
    RecapPage,
    Section,
    Status,
    Table,
)

logger = logging.getLogger(__name__)

# The AG Grid a recap opened outside DSS loads, unless the plugin settings give another. 29.2.0 is
# the version DSS 13.4.4 ships, so the grid behaves the same in and outside DSS.
AG_GRID_DEFAULT_URL = "https://cdn.jsdelivr.net/npm/ag-grid-community@29.2.0/dist/ag-grid-community.min.js"
AG_GRID_DEFAULT_INTEGRITY = "sha256-ytTx5Ih+kEK6CPSJN4iOP4d9cDw7IJ7HMtsvVwDh+aY="

# An integrity value, as the SRI standard writes it: one or more sha256, sha384 or sha512 hashes,
# separated by spaces, each with optional options after a "?".
INTEGRITY_HASH = r"sha(256|384|512)-[A-Za-z0-9+/]+={0,2}(\?[!-~]*)?"
INTEGRITY_PATTERN = rf"{INTEGRITY_HASH}(\s+{INTEGRITY_HASH})*"

FONT_FAMILY = (
    '"SourceSansPro", "Source Sans Pro", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, '
    '"Helvetica Neue", Arial, "Noto Sans", "Liberation Sans", sans-serif'
)

# Every rule starts with .dtp-recap so that it cannot change the rest of the DSS page.
# The font is the one of DSS in DSS, and the system font of each device in a downloaded recap.
# A downloaded recap has no doctype, so browsers render it in quirks mode, where tables do not
# inherit the font: the table sets it again.
STYLE = """
<style>
.dtp-recap { color: #22282e; font-size: 13px; line-height: 1.45; max-width: 1200px; }
.dtp-recap { box-sizing: border-box; padding-right: 16px; }
.dtp-recap, .dtp-recap table { font-family: __FONT_FAMILY__; }
.dtp-recap h3 { font-size: 14px; font-weight: 600; line-height: 1.3; margin: 0 0 6px; }
.dtp-recap h3 .dtp-note { font-weight: 400; }
.dtp-recap ul { margin: 4px 0 0; padding-left: 18px; }
.dtp-recap .dtp-context { color: #5c6670; margin: 0 0 16px; }
.dtp-recap .dtp-banner { background: #fff6dd; border-left: 4px solid #d99a00; margin: 0 0 12px; padding: 8px 12px; }
.dtp-recap .dtp-banner-danger { background: #fdecec; border-left-color: #c0272d; }
.dtp-recap .dtp-banner-muted { background: #eef1f4; border-left-color: #5c6670; }
.dtp-recap .dtp-metrics { display: flex; flex-wrap: wrap; gap: 8px; margin: 16px 0; }
.dtp-recap .dtp-metric { border: 1px solid #dfe3e7; border-radius: 4px; min-width: 92px; padding: 7px 10px; }
.dtp-recap .dtp-metric-value { display: block; font-size: 22px; font-weight: 600; }
.dtp-recap .dtp-metric-label { color: #5c6670; display: block; }
.dtp-recap .dtp-section { margin: 0 0 16px; }
.dtp-recap .dtp-tag { background: #eef1f4; border-radius: 3px; display: inline-block; }
.dtp-recap .dtp-tag { margin: 0 4px 4px 0; padding: 1px 6px; }
.dtp-recap .dtp-tag-caution { background: #fff6dd; }
.dtp-recap table { border-collapse: collapse; font-size: inherit; width: 100%; }
.dtp-recap th { border-bottom: 2px solid #dfe3e7; padding: 6px 8px; text-align: left; white-space: nowrap; }
.dtp-recap td { border-bottom: 1px solid #eef1f4; padding: 6px 8px; vertical-align: top; }
.dtp-recap .dtp-wrap { min-width: 160px; overflow-wrap: anywhere; }
.dtp-recap .dtp-nowrap { white-space: nowrap; }
.dtp-recap .dtp-number { text-align: right; }
.dtp-recap .dtp-success { color: #1d7a46; }
.dtp-recap .dtp-danger { color: #c0272d; }
.dtp-recap .dtp-muted { color: #5c6670; }
.dtp-recap .dtp-pending { color: #2f6fd8; }
.dtp-recap .dtp-caution { color: #b26a00; }
.dtp-recap .dtp-status { align-items: center; display: inline-flex; gap: 5px; white-space: nowrap; }
.dtp-recap .dtp-status svg { flex: none; height: 14px; width: 14px; }
.dtp-recap .dtp-toolbar { display: flex; gap: 8px; margin: 0 0 8px; }
.dtp-recap .dtp-toolbar input { flex: 1; margin: 0; }
.dtp-recap .dtp-grid { --ag-font-family: __FONT_FAMILY__; margin: 0 0 8px; width: 100%; }
.dtp-recap .dtp-grid .ag-cell { overflow: hidden; text-overflow: ellipsis; }
.dtp-recap .dtp-grid .dtp-wrap-cell { line-height: 1.4; padding-bottom: 5px; padding-top: 5px; white-space: normal; }
.dtp-recap .dtp-grid .dtp-wrap-cell { overflow-wrap: anywhere; word-break: normal; }
.dtp-recap .dtp-chips { display: flex; flex-wrap: wrap; gap: 3px; padding: 4px 0; }
.dtp-recap .dtp-chip {
  align-items: center; background: var(--ag-chip-background-color); border: 1px solid transparent;
  border-radius: calc(var(--ag-grid-size) * 4); display: inline-flex; height: calc(var(--ag-grid-size) * 4);
  line-height: 1; padding: 0 calc(var(--ag-grid-size) * 1.5); white-space: nowrap;
}
.dtp-recap .dtp-metric-filter { cursor: pointer; }
.dtp-recap .dtp-metric-on { border-color: #2f6fd8; box-shadow: inset 0 0 0 1px #2f6fd8; }
</style>
""".replace("__FONT_FAMILY__", FONT_FAMILY)

# Turns the static table into an AG Grid table: sorting, filters, search, CSV export, and the
# figures as status filters. DSS 13 ships AG Grid as window.agGrid, and runs the scripts of a
# macro's HTML. A recap opened on its own, outside DSS, loads AG Grid Community from the URL of the
# plugin settings. Without AG Grid, the static table stays. The rows come from the hidden JSON block
# of the table and are shown as text. Only Community features are used: the Enterprise modules in
# DSS are under the license of Dataiku.
GRID_SCRIPT = """
(function () {
  var root = document.getElementById("__ROOT_ID__");
  var staticTable = root && root.querySelector(".dtp-static-table");
  var columns = __COLUMNS__;
  var statuses = __STATUSES__;
  var texts = __TEXTS__;
  var cdn = __GRID_CDN__;
  var usable = function (lib) { return Boolean(lib && (lib.createGrid || lib.Grid)); };
  // A status the table does not list shows its code, last, with no icon: the grid keeps working.
  var statusOf = function (code) {
    return statuses[code] || {label: code == null ? "" : String(code), order: 1000, icon: ""};
  };
  if (!staticTable) {
    return;
  }
  if (usable(window.agGrid)) {
    build(window.agGrid);
  } else if (!window.angular && cdn.url) {
    // A recap opened on its own: load AG Grid Community from the URL of the plugin settings.
    // DSS pages always have AngularJS, so a second AG Grid never enters a DSS page.
    var script = document.createElement("script");
    script.src = cdn.url;
    if (cdn.integrity) {
      script.integrity = cdn.integrity;
      script.crossOrigin = "anonymous";
    }
    script.onload = function () {
      if (usable(window.agGrid)) { build(window.agGrid); }
    };
    document.head.appendChild(script);
  }

  function build(lib) {
    var toolbar = document.createElement("div");
    var container = document.createElement("div");
    try {
      var rows = JSON.parse(root.querySelector("script.dtp-table-data").textContent);
      var statusField = null;
      var statusFilter = null;
      var text = function (tag, className, value) {
        var element = document.createElement(tag);
        element.className = className;
        element.textContent = value;
        return element;
      };
      var tagList = function (params) {
        var chips = text("span", "dtp-chips", "");
        (params.value || []).forEach(function (tag) { chips.appendChild(text("span", "dtp-chip", tag)); });
        return chips;
      };
      var joined = function (params) { return (params.value || []).join(" "); };
      var columnDefs = columns.map(function (column) {
        var field = column.field;
        var def = {field: field, headerName: column.header, filter: "agTextColumnFilter"};
        if (column.fill) {
          def.flex = 1;
          def.minWidth = column.width;
        } else {
          def.width = column.width;
        }
        if (column.pinned) {
          def.pinned = "left";
        }
        if (column.kind === "status") {
          statusField = field;
          def.sort = "asc";
          def.comparator = function (a, b) { return statusOf(a).order - statusOf(b).order; };
          def.filterValueGetter = function (params) { return statusOf(params.data[field]).label; };
          def.cellRenderer = function (params) {
            // The icon is only shown: the CSV export takes the label, from processCellCallback.
            var status = text("span", "dtp-status", "");
            status.innerHTML = statusOf(params.value).icon;
            status.appendChild(document.createTextNode(statusOf(params.value).label));
            return status;
          };
        } else if (column.kind === "long_text") {
          def.wrapText = true;
          def.autoHeight = true;
          def.cellClass = "dtp-wrap-cell";
          def.tooltipField = field;
        } else if (column.kind === "tags") {
          def.wrapText = true;
          def.autoHeight = true;
          def.filterValueGetter = function (params) { return (params.data[field] || []).join(" "); };
          def.cellRenderer = tagList;
          def.valueFormatter = joined;
        } else if (column.kind === "number") {
          // numericColumn right aligns the header and the values. DSS styles its Balham cells as flex
          // boxes, which ignore text-align: justifyContent keeps the values on the right there, and
          // does nothing outside DSS. Neither changes the CSV export.
          def.type = "numericColumn";
          def.cellStyle = {justifyContent: "flex-end"};
          def.filter = "agNumberColumnFilter";
        }
        return def;
      });
      var options = {
        columnDefs: columnDefs,
        defaultColDef: {sortable: true, resizable: true, menuTabs: ["filterMenuTab"]},
        rowData: rows,
        domLayout: rows.length > 50 ? "normal" : "autoHeight",
        enableCellTextSelection: true,
        ensureDomOrder: true,
        suppressContextMenu: true,
        tooltipShowDelay: 300,
        isExternalFilterPresent: function () { return statusFilter !== null; },
        doesExternalFilterPass: function (node) { return node.data[statusField] === statusFilter; }
      };

      toolbar.className = "dtp-toolbar";
      var search = document.createElement("input");
      search.type = "search";
      search.placeholder = texts.search;
      var csv = text("button", "btn btn--secondary", "Export CSV");
      csv.type = "button";
      toolbar.appendChild(search);
      toolbar.appendChild(csv);
      container.className = "ag-theme-balham dtp-grid";
      if (options.domLayout === "normal") {
        container.style.height = "520px";
      }
      staticTable.parentNode.insertBefore(toolbar, staticTable);
      staticTable.parentNode.insertBefore(container, staticTable);

      var api;
      if (lib.createGrid) {
        api = lib.createGrid(container, options);
      } else {
        new lib.Grid(container, options);
        api = options.api;
      }
      staticTable.style.display = "none";

      search.addEventListener("input", function () {
        if (api.setGridOption) {
          api.setGridOption("quickFilterText", search.value);
        } else {
          api.setQuickFilter(search.value);
        }
      });
      csv.addEventListener("click", function () {
        api.exportDataAsCsv({
          fileName: texts.csvFileName,
          processCellCallback: function (params) {
            var value = params.value;
            if (Array.isArray(value)) { return value.join(", "); }
            if (params.column.getColId() === statusField) { return statusOf(value).label; }
            return value == null ? "" : value;
          }
        });
      });
      var metrics = root.querySelectorAll(".dtp-metric[data-status]");
      Array.prototype.forEach.call(metrics, function (metric) {
        metric.className += " dtp-metric-filter";
        metric.addEventListener("click", function () {
          var status = metric.getAttribute("data-status");
          statusFilter = status === "ALL" ? null : status;
          Array.prototype.forEach.call(metrics, function (other) {
            other.classList.toggle("dtp-metric-on", other === metric && statusFilter !== null);
          });
          api.onFilterChanged();
        });
      });
    } catch (error) {
      if (toolbar.parentNode) { toolbar.parentNode.removeChild(toolbar); }
      if (container.parentNode) { container.parentNode.removeChild(container); }
      staticTable.style.display = "";
      if (window.console) { window.console.warn("Recap: interactive table not available", error); }
    }
  }
})();
"""

# An icon before each status, in its colour: inline SVG, so it needs no font, in DSS or downloaded.
ICON_SHAPES = {
    ICON_CHECK: '<path d="M3 8.5l3 3 7-7"/>',
    ICON_CROSS: '<path d="M4 4l8 8M12 4l-8 8"/>',
    ICON_CLOCK: '<circle cx="8" cy="8" r="6"/><path d="M8 4.5V8l2.5 1.5"/>',
    ICON_WARNING: '<path d="M8 2l6.5 11.5h-13z"/><path d="M8 6.5v3M8 11.8v.2"/>',
    ICON_MINUS: '<circle cx="8" cy="8" r="6"/><path d="M5 8h6"/>',
    ICON_CIRCLE: '<circle cx="8" cy="8" r="6"/>',
}

BANNER_CLASSES = {
    TONE_CAUTION: "dtp-banner",
    TONE_DANGER: "dtp-banner dtp-banner-danger",
    TONE_MUTED: "dtp-banner dtp-banner-muted",
}


def text(value: Any) -> str:
    """Return a value as text that cannot add markup: dataset names, tags and DSS messages are free text."""
    return escape(str(value), quote=False)


def to_html_script_json(data: Any) -> str:
    """Return data as JSON that can sit inside a <script> element.

    Escaping <, > and & keeps a dataset name such as "</script>" from closing the element. JSON
    readers turn them back into the same characters.
    """
    json_text = json.dumps(data, ensure_ascii=False)
    return json_text.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


def count_of(count: int, noun: str) -> str:
    """Return "1 dataset" or "2 datasets": the count with its noun, in the singular for one."""
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def format_duration(seconds: float) -> str:
    """Format a duration for reading, such as "0.42 s" or "3.5 min"."""
    if seconds < 60:
        return f"{seconds:.2f} s"
    return f"{seconds / 60:.1f} min"


def format_started_at(started_at: str) -> str:
    """Turn "2026-11-02T19:10:00Z" into "2026-11-02 19:10:00 UTC"."""
    return started_at.replace("T", " ").replace("Z", " UTC")


def yes_no(value: bool) -> str:
    """Return "yes" or "no", for the options shown in a recap."""
    return "yes" if value else "no"


def build_common_option_chips(options: dict[str, Any]) -> list[Chip]:
    """Return the options of the "Run" section, if the form has it, and of the "Summary" section, for a recap."""
    chips = []
    if "on_error" in options:
        chips.append(Chip(f"{RUN_OPTION_LABELS['on_error']}: {RUN_ERROR_CHOICES[options['on_error']]}"))
    recap_dataset = "none"
    if options["recap_dataset"]:
        kept_or_replaced = "earlier runs kept" if options["recap_append"] else "replaced by this run"
        recap_dataset = f"{options['recap_dataset']}, {kept_or_replaced}"
    chips.append(Chip(f"{RECAP_OPTION_LABELS['recap_dataset']}: {recap_dataset}"))
    if options["recap_dataset"]:
        on_recap_error = RECAP_ERROR_CHOICES[options["on_recap_error"]]
        chips.append(Chip(f"{RECAP_OPTION_LABELS['on_recap_error']}: {on_recap_error}"))
    return chips


def with_outcome(summary: dict[str, Any], recap: dict[str, Any]) -> dict[str, Any]:
    """Return the summary of a macro with the outcome of the run and its problems, as every recap has them."""
    return {**summary, "outcome": recap["outcome"], "problems": [problem["message"] for problem in recap["problems"]]}


def build_icon(status: Status) -> str:
    """Build the icon of a status, in the colour of its tone."""
    return (
        f'<svg class="dtp-{status.tone}" viewBox="0 0 16 16" width="14" height="14" fill="none" '
        'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" '
        f'aria-hidden="true">{ICON_SHAPES[status.icon]}</svg>'
    )


def build_list(items: tuple[str, ...]) -> str:
    """Build a bulleted list of free texts."""
    return "<ul>" + "".join(f"<li>{text(item)}</li>" for item in items) + "</ul>"


def build_banner(banner: Banner) -> str:
    """Build a message the reader must see first."""
    words = []
    if banner.title:
        words.append(f"<strong>{text(banner.title)}</strong>")
    if banner.text:
        words.append(text(banner.text))
    items = build_list(banner.items) if banner.items else ""
    return f'<div class="{BANNER_CLASSES[banner.tone]}">{" ".join(words)}{items}</div>'


def build_outcome_banners(recap: dict[str, Any]) -> list[Banner]:
    """Return the banner of the outcome of the run, first in the recap: nothing when nothing went wrong."""
    messages = tuple(problem["message"] for problem in recap["problems"])
    if recap["outcome"] == OUTCOME_FAILED:
        return [Banner(TONE_DANGER, "The run failed after these errors:", items=messages)]
    if recap["outcome"] == OUTCOME_WARNING:
        return [Banner(TONE_CAUTION, "Warning: the run went on after these errors:", items=messages)]
    return []


def build_run_banners(recap: dict[str, Any]) -> list[Banner]:
    """Return the banners every recap has after those of the macro: the notices, and the recap dataset written."""
    # One banner per notice, as text: a list with no title above it would be indented.
    banners = [Banner(TONE_CAUTION, text=notice) for notice in recap["notices"]]

    result = recap["recap_dataset_result"]
    if result and not result["error"]:
        banners.append(
            Banner(
                TONE_MUTED,
                text=f"Summary written to dataset {result['name']}: {count_of(result['rows_written'], 'row')}.",
            )
        )
    return banners


def build_metric(metric: Metric) -> str:
    """Build one headline figure. With a status, the interactive table can filter on it."""
    status_attribute = f' data-status="{escape(metric.status)}"' if metric.status else ""
    tone_class = f" dtp-{metric.tone}" if metric.tone else ""
    return (
        f'<div class="dtp-metric"{status_attribute}>'
        f'<span class="dtp-metric-value{tone_class}">{text(metric.value)}</span>'
        f'<span class="dtp-metric-label">{text(metric.label)}</span>'
        "</div>"
    )


def build_chip(chip: Chip) -> str:
    """Build a short text in a grey box."""
    css_class = f"dtp-tag dtp-tag-{chip.tone}" if chip.tone else "dtp-tag"
    return f'<span class="{css_class}">{text(chip.text)}</span>'


def build_section(section: Section) -> str:
    """Build a titled block of chips or text, such as the options of the run."""
    title = text(section.title)
    if section.note:
        title += f' <span class="dtp-note">{text(section.note)}</span>'
    chips = "".join(build_chip(chip) for chip in section.chips)
    return f'<div class="dtp-section"><h3>{title}</h3>{chips}{text(section.text)}</div>'


def build_cell(column: Column, value: Any, statuses: dict[str, Status]) -> str:
    """Build one cell of the static table. A status the table does not list shows its code, with no icon."""
    if column.kind == COLUMN_STATUS:
        status = statuses.get(value)
        if status is None:
            return f'<td><span class="dtp-status">{text(value)}</span></td>'
        return f'<td><span class="dtp-status">{build_icon(status)}{text(status.label)}</span></td>'
    if column.kind == COLUMN_TAGS:
        return "<td>" + "".join(f'<span class="dtp-tag">{text(tag)}</span>' for tag in value or []) + "</td>"
    shown = "" if value is None else text(value)
    if column.kind == COLUMN_NUMBER:
        return f'<td class="dtp-nowrap dtp-number">{shown}</td>'
    if column.kind == COLUMN_LONG_TEXT or column.pinned:
        return f'<td class="dtp-wrap">{shown}</td>'
    return f"<td>{shown}</td>"


def build_table(table: Table) -> str:
    """Build the static table, sorted by status, and the hidden JSON block of its rows for the grid script."""
    if not table.rows:
        return f"<p>{text(table.empty_message)}</p>"

    statuses = {status.code: status for status in table.statuses}
    status_fields = [column.field for column in table.columns if column.kind == COLUMN_STATUS]
    rows = table.rows
    if status_fields:
        order = {status.code: index for index, status in enumerate(table.statuses)}
        rows = sorted(rows, key=lambda row: order.get(row[status_fields[0]], len(order)))

    headers = "".join(
        f'<th class="dtp-number">{text(column.header)}</th>'
        if column.kind == COLUMN_NUMBER
        else f"<th>{text(column.header)}</th>"
        for column in table.columns
    )
    body = "".join(
        "<tr>" + "".join(build_cell(column, row.get(column.field), statuses) for column in table.columns) + "</tr>"
        for row in rows
    )
    return (
        f'<h3>{text(table.title)}</h3><div class="dtp-static-table"><table><thead><tr>{headers}</tr></thead>'
        f"<tbody>{body}</tbody></table></div>"
        f'<script type="application/json" class="dtp-table-data">{to_html_script_json(table.rows)}</script>'
    )


def read_grid_cdn(plugin_config: Optional[dict[str, Any]]) -> dict[str, str]:
    """Return the AG Grid a recap opened outside DSS loads, from the plugin settings: {"url", "integrity"}.

    A missing setting takes its default. An empty URL turns the loading off. So does a URL that is
    not http(s), since a downloaded recap is opened from a file, or an integrity that is not made of
    sha256, sha384 or sha512 hashes: a browser would load the file unchecked.
    """
    config = plugin_config or {}
    url = str(config.get("ag_grid_url", AG_GRID_DEFAULT_URL) or "").strip()
    integrity = str(config.get("ag_grid_integrity", AG_GRID_DEFAULT_INTEGRITY) or "").strip()
    off = {"url": "", "integrity": ""}
    if not url:
        return off
    if not re.match(r"https?://", url):
        logger.warning("AG Grid URL of the plugin settings ignored, it is not http(s): %s", url)
        return off
    if integrity and not re.fullmatch(INTEGRITY_PATTERN, integrity):
        logger.warning("AG Grid integrity of the plugin settings ignored, it is not a hash: %s", integrity)
        return off
    return {"url": url, "integrity": integrity}


def build_grid_script(root_id: str, table: Table, grid_cdn: dict[str, str]) -> str:
    """Build the script that turns the static table into an AG Grid table, or "" without rows.

    It holds no data: it reads the rows from the hidden JSON block of the table. Its settings go in as
    JSON that cannot close the script element.
    """
    if not table.rows:
        return ""
    columns = [column._asdict() for column in table.columns]
    statuses = {
        status.code: {"label": status.label, "order": index, "icon": build_icon(status)}
        for index, status in enumerate(table.statuses)
    }
    texts = {"search": table.search_placeholder, "csvFileName": table.csv_file_name}
    script = (
        GRID_SCRIPT.replace("__ROOT_ID__", root_id)
        .replace("__COLUMNS__", to_html_script_json(columns))
        .replace("__STATUSES__", to_html_script_json(statuses))
        .replace("__TEXTS__", to_html_script_json(texts))
        .replace("__GRID_CDN__", to_html_script_json(grid_cdn))
    )
    return f"<script>{script}</script>"


def build_recap_html(recap: dict[str, Any], page: RecapPage, grid_cdn: Optional[dict[str, str]] = None) -> str:
    """Build the full recap.

    It has no title of its own: DSS shows "Result" above the HTML of a macro, and the plugin cannot
    change it (resultLabel only names the links and files a macro returns).

    Free text always goes through text(). ng-non-bindable is also required: DSS runs a macro's HTML
    through AngularJS, which would execute a tag such as {{...}} in the reader's browser. So every
    value from the project sits inside that element, and the grid script after it holds none.

    The hidden JSON block holds the summary of the macro, with the outcome of the run and its
    problems, for the code that runs the macro through the API. A browser never runs nor displays a
    script of type application/json.

    The meta tag keeps accents readable in the report downloaded from DSS.

    :param recap: the recap of the run, for the fields every recap has
    :param page: what the macro shows
    :param grid_cdn: the AG Grid to load outside DSS, from read_grid_cdn(); the default one if None
    """
    root_id = f"dtp-recap-{recap['run_id']}"
    context = (
        f"{text(recap['macro_label'])} · Project {text(recap['project_key'])} · "
        f"Run by {text(recap['run_by'] or 'unknown user')} · Started {text(format_started_at(recap['started_at']))}"
    )
    banners = build_outcome_banners(recap) + page.banners + build_run_banners(recap)
    summary = to_html_script_json(with_outcome(page.summary, recap))
    return (
        '<meta charset="utf-8">'
        f"{STYLE}"
        f'<div class="dtp-recap" id="{root_id}" ng-non-bindable>'
        f'<p class="dtp-context">{context}</p>'
        f"{''.join(build_banner(banner) for banner in banners)}"
        f'<div class="dtp-metrics">{"".join(build_metric(metric) for metric in page.metrics)}</div>'
        f"{''.join(build_section(section) for section in page.sections)}"
        f"{build_table(page.table)}"
        f'<script type="application/json" id="dtp-recap-data">{summary}</script>'
        "</div>"
        f"{build_grid_script(root_id, page.table, read_grid_cdn(None) if grid_cdn is None else grid_cdn)}"
    )
