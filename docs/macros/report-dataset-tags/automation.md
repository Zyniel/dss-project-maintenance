# Report Dataset Tags: automation

Run the macro from a scenario or from the API, and read its results as data.

## Scenarios

The macro changes nothing, so it is safe to run it often, for example each week, to follow how tags are used.

The macro changes nothing, so it has no "If an error occurs" option. Only the summary dataset can fail: choose what to do in **If the summary is not written**:

- "Continue" (the default): the run is a success. The recap shows a yellow banner at the top, and the JSON recap has `"outcome": "WARNING"`. DSS cannot show a macro run as a warning.
- "Fail the run": the scenario step turns red. Choose it when the summary dataset keeps a history: a run that is not written leaves a hole in it.

## Summary dataset

Check **Write to a dataset** and pick a dataset of the project in **Summary dataset**. Use a new, empty, managed dataset. The macro never writes into a dataset that has other columns.

The dataset gets one row per tag and dataset, and per run:

- a tag on 3 datasets gives 3 rows;
- an unused tag gives 1 row, with an empty `dataset`;
- a dataset with no tag gives 1 row, with an empty `tag` and the status `UNTAGGED`.

With "Append mode" checked (the default), each run adds its rows: you get a history of the tags of the project. In DSS, group the rows by `run_started_at` and `tag` to see how a tag is used over time.

All columns are text:

| Column | Content |
|---|---|
| `run_id` | Id of the run, the same for all its rows. |
| `run_started_at` | Start of the run in UTC, for example `2026-11-02T19:10:00Z`. |
| `macro` | Id of the macro: `report-dataset-tags`. |
| `project_key` | The project where the macro ran. |
| `run_by` | The login of the user who ran it. |
| `tag` | The tag, or empty for a dataset with no tag. |
| `tag_category` | The category of the tag (`Stage` for `Stage:Raw`), or empty. |
| `tag_status` | `USED`, `UNKNOWN`, `UNUSED` or `UNTAGGED`. |
| `dataset` | The dataset, or empty for an unused tag. |
| `dataset_type` | The type of the dataset, or empty. |

## The run log

The log gives a line per tag with its status and its number of datasets, then the datasets with no tag, then the totals, then a line that starts with `RECAP_JSON` with the whole recap as JSON (see [The JSON recap](#the-json-recap)).

## The API

DSS gives the result of a macro only once: after `get_result`, the run does not exist any more.

```python
import json
import re

import dataiku

project = dataiku.api_client().get_default_project()
macro = project.get_macro("pyrunnable_project-maintenance_report-dataset-tags")
run_id = macro.run(params={"show_unused_tags": True})
html = macro.get_result(run_id, as_type="string")
if isinstance(html, bytes):  # The API client can return bytes.
    html = html.decode("utf-8")
block = re.search(r'<script type="application/json" id="dtp-recap-data">(.*?)</script>', html, re.DOTALL)
recap = json.loads(block.group(1))
print(recap["counts"])
```

### Macro id

`pyrunnable_project-maintenance_report-dataset-tags`

### Parameters

| Parameter | Type | Default |
|---|---|---|
| `show_unused_tags` | boolean | `true` |
| `aggregate_by_tag` | boolean: `false` gives one row per tag and dataset in the HTML table | `true` |
| `recap_to_dataset` | boolean: `false` ignores `recap_dataset` | `true` if `recap_dataset` is given |
| `recap_dataset` | dataset name, or `PROJECTKEY.name` of this project | none |
| `recap_append` | boolean | `true` |
| `on_recap_error` | `"CONTINUE"` or `"FAIL"` | `"CONTINUE"` |

A missing parameter takes its default value. Only a real `true` or `false` counts, and only `"CONTINUE"` or `"FAIL"` for `on_recap_error`: any other value takes the default.

## The JSON recap

The same JSON is in the hidden block of the HTML and on the `RECAP_JSON` line of the log.

| Field | Content |
|---|---|
| `run_id`, `macro`, `project_key`, `run_by`, `started_at` | The run. |
| `outcome` | `"SUCCESS"`, `"WARNING"` (the summary dataset was not written, and the run went on) or `"FAILED"`. |
| `problems` | What went wrong: here, only the summary dataset. |
| `options` | The options used, with the same names as the parameters. |
| `categories_checked` | If the tag categories of DSS could be read. |
| `notices` | What the reader must know. |
| `counts` | `datasets`, `tagged`, `untagged`, `tags`, `used`, `unknown`, `unused`. |
| `duration_seconds` | Total duration. |
| `recap_dataset` | `null`, or `{"name", "rows_written", "error"}`. |
| `tags` | One object per tag: `tag`, `category`, `status`, `detail`, `dataset_count`, `datasets`. |
| `untagged_datasets` | The names of the datasets with no tag. |
