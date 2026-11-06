# Architecture

How the code is split, which rules keep it clean, and the steps of a run.

## The three parts of the code

All the code is in `python-lib/dss_maintenance`. It does not depend on DSS: you can test it on your computer.

```
python-lib/dss_maintenance/
  core/                  Shared by all macros
    macro.py               MaintenanceMacro: what each macro must provide
    runner.py              run_macro(): runs a macro, from start to end
    options.py             Reads the form: the "Summary" section of every form, the "Run" section of macros that change data
    project.py             Reads a project: datasets, sharing, Flow
    tags.py                Selects datasets: all of them or by included tags, then excluded tags
  recap/                 Shared by all macros
    page.py                RecapPage: the description of a recap (banners, figures, table...)
    html.py                Builds the HTML recap and its interactive table
    dataset.py             Writes the summary dataset
  macros/                One folder per macro
    clear_datasets_by_tags/
      __init__.py            Exposes MACRO
      macro.py               The class of the macro, which connects the two next files
      cleanup.py             The work: read the form, decide, clear
      recap.py               The content of the recap: JSON, rows of the summary dataset, HTML page
    report_dataset_tags/   Same layout, with report.py for the work: read and count the tags
```

Only the files that DSS calls import `dataiku`:

| File | DSS calls it to |
|---|---|
| `python-runnables/<macro>/runnable.py` | Run the macro. It calls `run_macro()` with the macro, the API client and a function that opens a dataset. |
| `resource/tag_choices.py` | Fill the "Cat. Tags" lists of a form. It calls `list_category_tag_choices()`. |

## The import rules

These rules keep the macros independent. `tests/plugin/test_import_rules.py` checks them.

- `core` and `recap` never import a macro.
- A macro never imports another macro. If two macros need the same code, it goes into `core` or `recap`.
- `runnable.py` imports only its own macro and the shared code. A file of `resource/` imports only the shared code.
- Nothing in `python-lib` imports `dataiku`.
- Imports are absolute: `from dss_maintenance.core.tags import matches`, never `from .tags import matches`.

**When to share code?** When a second macro needs it, not before. For example, `clear_dataset()` stays in `clear_datasets_by_tags` while no other macro clears datasets.

## What a macro provides

Each macro defines a subclass of `MaintenanceMacro` (in `core/macro.py`) and one instance of it, named `MACRO`.

| Item | Use |
|---|---|
| `id` | The name of its folder in `python-runnables`, for example `clear-datasets-by-tags`. |
| `label` | Its name on the Macros page, the same as in its `runnable.json`. |
| `recap_columns` | The columns of its summary dataset. |
| `run()` | Does the work and returns the recap (a dict). Raises `ValueError` if the form is not valid, and `RunStopped` if a real run must stop. Both happen before anything changes. |
| `describe_counts()` | The totals of the run, for the log. |
| `build_recap_rows()` | The rows of the summary dataset. |
| `build_recap_page()` | The description of the HTML recap (`RecapPage`), with the recap as JSON in its `summary`: for the API, the hidden block of the HTML and the `RECAP_JSON` log line. |
| `describe_failures()` | What failed in the work, such as the datasets that could not be cleared, or `""`. A macro that only reads returns `""`. |

The dict that `run()` returns has at least `options`, `notices` and `blockers`. A macro that changes data also returns `simulate`. Then the runner adds the fields that every recap has: `run_id`, `macro`, `macro_label`, `project_key`, `run_by`, `started_at`, `duration`, `recap_dataset_result`, `problems` and `outcome`.

The smallest possible macro is in `tests/support/sample_macro.py`. The tests of the shared code use it.

## The steps of a run

`run_macro()` in `core/runner.py`:

1. **Who runs the macro:** reads the login with `client.get_auth_info()`. If this fails, the login stays empty.
2. **The work:** calls `macro.run()`, then adds the common fields to the recap.
3. **The summary dataset:** if the form asks for it, writes it. A failure is written in the recap and does not stop the run: the work is already done.
4. **The outcome:** lists the problems, the work first (`macro.describe_failures()`), then the summary dataset. Each problem fails the run only if its option asks for it: "Continue, run ends in error" or "Raise exception" in "If an error occurs" for the work, "Fail the run" in "If the summary is not written" for the summary dataset. With "Raise exception", the macro itself stops its work at the first error. The outcome is:
   - `SUCCESS`: no problem;
   - `WARNING`: problems, and the run goes on. DSS shows the run as a success: it cannot show a macro run as a warning. So the recap shows a yellow banner at the top;
   - `FAILED`: a problem whose option asks to end the run in error.
5. **The log:** writes the totals, one line per problem (WARNING, or ERROR when it fails the run), the outcome, then the `RECAP_JSON` line with the whole recap, then waits half a second. Without this wait, DSS 13.4.4 once lost this last line.
6. **The HTML recap:** builds it from `macro.build_recap_page()`, with the outcome banner first.
7. **The end:** if the outcome is `FAILED`, raises `RunFailed`. Its message gives every problem, then where the full recap is. Otherwise, returns the HTML.

| Error | Raised by | When |
|---|---|---|
| `ValueError` | `macro.run()` | The form is not valid. Nothing changed. |
| `RunStopped` | `macro.run()` | A real run must stop. Nothing changed. |
| `RunFailed` | `run_macro()` | A problem whose option asks to end the run in error. The summary dataset and the log are written first. |

DSS shows the message of the error as the result of the run.

## The HTML recap

Each macro describes its recap with a `RecapPage` (`recap/page.py`). `recap/html.py` builds the page the same way for all macros:

1. the context: macro, project, who ran it, when;
2. the banners (`Banner`) of the macro, then the notices of the run and the result of the summary dataset;
3. the figures (`Metric`). A click on a figure with a status filters the table;
4. the sections (`Section`), for example the options and the tags;
5. the table (`Table`), described by its columns (`Column`) and its statuses (`Status`).

Kinds of columns:

| Kind | Shows |
|---|---|
| `COLUMN_TEXT` | Text on one line. |
| `COLUMN_LONG_TEXT` | Text on several lines if needed. |
| `COLUMN_STATUS` | The icon and the label of the status. The table is sorted by status, failures first. |
| `COLUMN_TAGS` | A list, shown as chips. |
| `COLUMN_NUMBER` | A number, aligned on the right. `None` shows nothing. |

The HTML contains a simple table. In DSS, a script replaces it with an AG Grid table: sort, filters, search, CSV export. DSS 13 provides AG Grid in its pages (`window.agGrid`). A downloaded recap, opened alone, loads AG Grid Community from the URL of the plugin settings. Without AG Grid, the simple table stays.

## Security

- **No extra rights.** The macros run with the rights of the user (`"impersonate": true`).
- **Escaped text.** Dataset names, tags and DSS messages are free text: they all go through `text()` (`html.escape`).
- **No AngularJS.** DSS shows the HTML of a macro without filtering it, and passes it through AngularJS. The whole recap is inside an element with `ng-non-bindable`: a `{{...}}` in a dataset name is not evaluated.
- **Inactive JSON blocks.** The recap and the rows of the table are in `<script type="application/json">` blocks, which the browser does not run. `<`, `>` and `&` are escaped inside, so a name like `</script>` cannot close the block.
- **A script with no data.** The script of the table contains no data of the project: it reads the JSON block and shows each value as text.
- **AG Grid Community only.** The Enterprise modules that DSS contains are under the license of Dataiku.
- **A CDN only outside DSS.** The script loads AG Grid only on a page without AG Grid and without AngularJS, so never in DSS. The browser checks the file with its hash.

## The DSS API calls

| Call | Used to | Note |
|---|---|---|
| `project.list_datasets()` | List the datasets with `projectKey`, `name`, `type`, `managed`, `tags`, `params.connection`, `partitioning.dimensions`. | Without `managed`, a dataset counts as external. |
| `project.get_settings().get_raw()["exposedObjects"]` | Find the datasets shared with other projects. | Only for project administrators. |
| `project.get_flow().get_graph().get_source_computables()` | Find the datasets that no recipe builds. | |
| `project.get_dataset(name).clear()` | Clear a dataset, all partitions included. | DSS reports a failure in the answer (`error`, `fatal`), and does not raise. |
| `project.get_tags()` | Read the project tag list. | It also holds the tags of other objects, such as recipes. |
| `project.client.get_general_settings().get_raw()["globalTagsCategories"]` | Read the tag categories of DSS, with their tags. | Only for DSS administrators. |
| `client.get_auth_info()["authIdentifier"]` | Know who runs the macro. | |
| `dataiku.default_project_key()` | Know the project where the form is open. | Works on DSS 13.4.4. |
| `dataiku.Dataset(...)` | Write the summary dataset. | Outside a recipe, a write replaces the data. With "Append mode", the macro sets `spec_item["appendMode"]` before `get_writer()`: the write session of DSS then appends the rows. |
| `window.agGrid` in the DSS page | Build the interactive table. | Not a public API: DSS 13.4.4 provides AG Grid 29.2. |
