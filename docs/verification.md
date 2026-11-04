# Verification

What the tests prove, and what to check on a real DSS.

## What is proven

| What | How |
|---|---|
| The shared code and each macro | 349 tests with fake DSS objects, on Python 3.9 and 3.13. |
| The forms match the code, `runnable.py` loads, the import rules are respected | Tests of `tests/plugin`, for each macro. |
| The DSS API calls exist, with the expected shape | Read in the code of the public API client, `dataiku-api-client` 15.2.1. |
| The plugin works on a real DSS | Run on a local DSS 13.4.4 container: see the checks below. |

The fake objects copy what the code expects from DSS. Only a real DSS shows if it really answers that way.

## Check on DSS 13

Use an instance with a license, for example a local DSS 13.4.4 container, and follow these rules:

- **Test projects only:** create test projects, never touch existing projects.
- **Licenses:** a test user can take a license seat. Prefer existing users.
- **Clean up:** at the end, delete the test projects, the test users and the API keys.

For each check, write the result and the date. If DSS answers in another way, fix the code and the fake objects of `tests/support/fakes.py` together.

### The plugin

| # | Check | What the code expects | Result |
|---|---|---|---|
| 1 | Python version of the built-in environment | 3.9 | OK: 3.9.20, with pandas 2.2.3. |
| 2 | Install the zip of `uv run python build_plugin_zip.py` | The plugin installs with its default settings. | OK, 13.4.4, 2026-11-03. |
| 3 | The Macros page of a project | The macros are in the "Project maintenance" section (`meta.category`). | OK, 13.4.4, 2026-11-03. Without `meta.category`, DSS uses the plugin id as the section name. |
| 4 | The interactive table of the recap in DSS | `window.agGrid` exists in the page, and the scripts of the HTML of a macro run. | OK, 13.4.4, 2026-11-03: the grid replaces the simple table, with columns, icons and chips. "Duration (s)" is aligned on the right. No message in the console. |
| 5 | A recap opened alone, outside DSS | It loads AG Grid Community 29.2.0 from the URL of the settings, with the hash, and never inside DSS. | OK, 2026-11-03: a recap served as a page alone loads AG Grid from jsDelivr with its hash, and shows the interactive table. |
| 6 | The HTML of the recap in DSS | DSS shows the HTML without filtering it: a `{{...}}` or `<b>` in a tag must stay text. | OK, 13.4.4, 2026-11-03: the tag `<b>bold</b>{{7*7}}` shows as text. |
| 7 | The `RECAP_JSON` line of the log, for a run from the UI | It is the last line of the macro. | Lost once: DSS stops reading the log as soon as the macro returns. OK since the macro waits half a second. |
| 8 | `"permissions": ["WRITE_CONF"]` | Users who can write in the project see the macro. Other users do not. | To do. |

### Clear Datasets by Tags

| # | Check | What the code expects | Result |
|---|---|---|---|
| 9 | A simulation, then a real run, from the API | The figures, the JSON block and the summary dataset are correct. | OK, 13.4.4, 2026-11-03: 2 cleared, 1 excluded, 3 rows in the summary dataset. |
| 10 | The fields of `list_datasets()` for a managed, editable, uploaded, external and partitioned dataset | `managed`, `partitioning.dimensions`, `tags` and `params.connection` are present. | Managed dataset only: OK. The others: to do. |
| 11 | The answer of `clear()` after a success, then after a failure | A failure sets `error` or `fatal`. `success` can be false after a success. | Success: OK. Failure: to do. |
| 12 | `get_flow().get_graph().get_source_computables()` | Datasets with no recipe are `COMPUTABLE_DATASET` nodes, with their name in `ref`. | OK. |
| 13 | Who can read `get_settings()`, which contains the sharing | Project admin and instance admin: yes. Simple editor: no. | Instance admin: OK. The others: to do. |
| 14 | The value of a `DATASET` parameter | The dataset name, or `PROJECTKEY.name`. | OK. |
| 15 | Write the summary dataset from a macro | `dataiku.Dataset(name, project_key=..., ignore_flow=True)` supports `read_schema`, `write_schema` and `get_writer`, and `spec_item["appendMode"] = True` makes the writer append. | Written with its schema, from the API and the UI. Append mode OK, 13.4.4, 2026-11-04: two runs gave 7 then 14 rows from two runs, and a run with "Append mode" unchecked replaced them with 7 rows. Two runs at the same time: not checked. |
| 16 | "Write to a dataset" checked, a dataset picked, then unchecked | "Summary dataset" and "Append mode" are hidden, and nothing is written. | OK. |
| 17 | `macro.get_result(run_id, as_type="string")` | It can return bytes. The JSON of `<script id="dtp-recap-data">` can be read. | OK: bytes, and the JSON can be read. |
| 18 | "If an error occurs" set to "Continue, run ends in error" or "Raise exception", in a scenario | DSS shows the error message, and the scenario step turns red. "Raise exception" stops at the first dataset that cannot be cleared. | To do. |
| 19 | The "Cat. Tags" lists | `resource/tag_choices.py` imports from `python-lib`, and `dataiku.default_project_key()` gives the project of the form. | OK as instance admin. DSS shows them as a tag input, without the groups. Simple editor: to do. |
| 20 | A category tag picked only in "Included Cat. Tags" | The form sends nothing in "Excluded Cat. Tags". | OK. |

### Report Dataset Tags

| # | Check | What the code expects | Result |
|---|---|---|---|
| 21 | `project.get_tags()` | `{"tags": {<tag>: {...}}}`. DSS adds a tag to the list when an object gets it, and keeps it after. | OK, 13.4.4, 2026-11-03. |
| 22 | The global tag categories | In the general settings, `globalTagsCategories`: a list of `{"name", "globalTags": [{"name", "color"}], "appliesTo"}`. Only DSS administrators can read them. | Shape OK, 13.4.4, 2026-11-03. A user who is not a DSS administrator: to do. |
| 23 | A run from the API and from the UI | The figures, the table (problems first), the figure filters and the summary dataset are correct, with "Aggregate by tag" checked and unchecked. | OK, 13.4.4, 2026-11-03: 2 unknown tags, 1 unused tag, 3 datasets with no tag, 8 rows in the summary dataset. Checked: 6 rows, dataset names as text. Unchecked: 8 rows, one per tag and dataset. No message in the console. |
| 24 | `"permissions": ["READ_CONF"]` | A user who can only read the project sees and runs the macro. | To do: the test instance has no such user. |
| 25 | "If the summary is not written" with a summary dataset that cannot be written | "Continue": the run succeeds, with the outcome WARNING and a yellow banner. "Fail the run": the run fails with the message. "If an error occurs" does not cover it. | OK, 13.4.4, 2026-11-04, from the API, with Report Dataset Tags and Clear Datasets by Tags. Both select lists show in the forms with "Continue" and "Fail the run". |
| 26 | The form after a plugin update | It shows the defaults of `runnable.json`. | DSS remembers the values of the last run in the local storage of the browser, under the key `<project key>.<macro id>`: one entry per project and per browser. "Clear shared datasets" stayed unchecked after a plugin update that checked it by default, in a test project recreated with the same key. "Reset to default" shows the new defaults. Read in the DSS 13.4.4 frontend (`runnables.js`), 2026-11-04. |
| 27 | The plugin setting "Tag categories" | Set to `Stage`, the "Cat. Tags" lists offer only the tags of that category. Empty: all categories. | OK, 13.4.4, 2026-11-04: the setting shows under "Tag lists" in the plugin settings, and the lists offered only the tags of the chosen category, not those of the other categories. |

## Not covered yet

These datasets are cleared like the others. They could get their own option, once checked on a real DSS:

- **Write-protected datasets:** the rebuild behavior of a dataset can be "write-protected".
- **Append outputs:** outputs of recipes that append instead of overwrite. Clearing them loses their history, even if a recipe builds them.
