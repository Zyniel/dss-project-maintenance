# Clear Datasets by Tags: automation

Run the macro from a scenario or from the API, and read its results as data.

## Scenarios

Two options say what to do when something goes wrong.

**If an error occurs**, in the "Run" section, covers a dataset that could not be cleared:

| Choice | Value | What happens |
|---|---|---|
| Continue, run ends as success | `CONTINUE` | Every dataset is tried. The run is a success. This is the default. |
| Continue, run ends in error | `FAIL` | Every dataset is tried. Then the run ends in error. |
| Raise exception | `STOP` | The clearing stops at the first dataset that cannot be cleared. The datasets after it are skipped, with the skip code `STOPPED`. Then the run ends in error. |

**If the summary is not written**, in the "Summary" section, covers the summary dataset that could not be written. The datasets are cleared anyway. Its choices are "Continue" (the default) and "Fail the run".

In a scenario, choose a choice that ends the run in error: then the scenario step that runs the macro turns red. The message names the problems, for example: "2 of 14 datasets to clear failed: a, b. The other 12 were cleared." With "Raise exception", it also says how many datasets were not tried. In every case, the summary dataset is written and the log has the `RECAP_JSON` line before the run ends.

Keep the defaults when you run the macro by hand: a failed run shows only its message, not the recap.

With "Continue", DSS shows the run as a success, even when something went wrong. DSS cannot show a macro run as a warning. So the recap shows a yellow banner at the top: "Warning: the run went on after these errors". The log has a WARNING line for each problem, and the JSON recap has `"outcome": "WARNING"`.

A run also ends in error, before it clears anything, when the form is not valid or when a [check](user-guide.md#checks-before-clearing) stops it. This does not depend on these options.

## Summary dataset

Check **Write to a dataset** and pick a dataset of the project in **Summary dataset**: it gets one row per selected dataset and per run. Use a new, empty, managed dataset. The macro never writes into a dataset that has other columns.

The dataset picker of DSS has no empty entry: uncheck **Write to a dataset** to stop using a dataset picked before. Checked with no dataset picked, the run stops before it clears anything.

All columns are text:

| Column | Content |
|---|---|
| `run_id` | Id of the run, the same for all its rows. |
| `run_started_at` | Start of the run in UTC, for example `2026-11-02T19:10:00Z`. |
| `macro` | Id of the macro: `clear-datasets-by-tags`. |
| `project_key` | The project where the macro ran. |
| `run_by` | The login of the user who ran it. |
| `simulate` | `true` or `false`. |
| `dataset`, `dataset_type` | The selected dataset and its type. |
| `status` | `CLEARED`, `WOULD_BE_CLEARED`, `FAILED`, `SKIPPED` or `EXCLUDED`. |
| `skip_code` | For a skipped dataset: `EXTERNAL`, `SHARED`, `PARTITIONED`, `WITHOUT_RECIPE`, `RECAP_DATASET`, or `STOPPED` (not tried: the run stopped at the first error). |
| `detail` | The reason, the message of DSS, or the error. |
| `warnings` | The warnings, separated by ` \| `. |
| `included_tags`, `excluded_tags` | The included and excluded tags of the dataset, separated by `, `. |
| `is_shared` | `true`, `false`, or empty if the sharing could not be read. |
| `shared_with` | The projects the dataset is shared with. |
| `built_by_recipe` | `true`, `false`, or empty if the Flow could not be read. |
| `partition_dimensions` | The partition dimensions, separated by `, `. |
| `clear_duration_seconds` | Duration of the clear, empty if nothing was cleared. |

**Append mode** is checked by default: earlier runs are kept. The macro writes with the append mode of DSS: each run adds its rows, and never reads nor writes the earlier ones again. Two runs that write at the same time both keep their rows. A run with no selected dataset does not touch the summary dataset.

**Each run replaces the content** when "Append mode" is unchecked.

## The run log

The last lines of the log give the totals, then a line that starts with `RECAP_JSON`, with the whole recap as JSON (see [The JSON recap](#the-json-recap)). The lines before give the tags read, the options, the decision for each dataset with its reason, then the result of each clear.

## The API

DSS gives the result of a macro only once: after `get_result`, the run does not exist any more.

The HTML recap contains the whole recap as JSON (see [The JSON recap](#the-json-recap)) in a hidden block:

```python
import json
import re

import dataiku

project = dataiku.api_client().get_default_project()
macro = project.get_macro("pyrunnable_project-maintenance_clear-datasets-by-tags")
run_id = macro.run(
    params={
        "included_tags": ["temporary"],
        "included_category_tags": ["Department:Marketing"],
        "excluded_tags": ["keep"],
        "simulate": False,
    }
)
html = macro.get_result(run_id, as_type="string")
if isinstance(html, bytes):  # The API client can return bytes.
    html = html.decode("utf-8")
block = re.search(r'<script type="application/json" id="dtp-recap-data">(.*?)</script>', html, re.DOTALL)
recap = json.loads(block.group(1))
print(recap["counts"])
```

A failed run, for example with a form that is not valid, raises an error in `get_result`, with its message.

### Macro id

`pyrunnable_project-maintenance_clear-datasets-by-tags`

### Parameters

| Parameter | Type | Default |
|---|---|---|
| `included_tags` | list of texts | none |
| `included_category_tags` | list of `"<category>:<value>"` texts | none |
| `included_match` | `"ANY"` or `"ALL"` | `"ANY"` |
| `excluded_tags` | list of texts | none |
| `excluded_category_tags` | list of `"<category>:<value>"` texts | none |
| `excluded_match` | `"ANY"` or `"ALL"` | `"ANY"` |
| `simulate` | boolean | `true` |
| `purge_partitioned` | boolean | `false` |
| `purge_shared` | boolean | `true` |
| `purge_without_recipe` | boolean | `false` |
| `on_error` | `"CONTINUE"`, `"FAIL"` or `"STOP"` | `"CONTINUE"` |
| `recap_to_dataset` | boolean: `false` ignores `recap_dataset` | `true` if `recap_dataset` is given |
| `recap_dataset` | dataset name, or `PROJECTKEY.name` of this project | none |
| `recap_append` | boolean | `true` |
| `on_recap_error` | `"CONTINUE"` or `"FAIL"` | `"CONTINUE"` |

A missing parameter takes its default value. The two fields of a list are merged: a category tag can go in either one.

Only a real `true` or `false` counts, and only the values above for `on_error` and `on_recap_error`. Any other value takes the default:

- a simulation;
- shared datasets cleared, partitioned and recipe-less datasets skipped;
- earlier runs kept in the summary dataset.

## The JSON recap

The same JSON is in the hidden block of the HTML and on the `RECAP_JSON` line of the log.

| Field | Content |
|---|---|
| `run_id`, `macro`, `project_key`, `run_by`, `started_at`, `simulate` | The run. |
| `outcome` | `"SUCCESS"`, `"WARNING"` (something went wrong, and the run went on) or `"FAILED"`. |
| `problems` | What went wrong: the datasets that could not be cleared, then the summary dataset. |
| `options` | The options used, with the same names as the parameters. |
| `included_tags`, `included_match`, `excluded_tags`, `excluded_match` | The tags read in the form, each list merged, and "Any" or "All". |
| `included_tag_counts`, `excluded_tag_counts` | The number of datasets that have each tag. |
| `sharing_checked`, `recipes_checked` | If each check was possible. |
| `notices` | What the reader must know. The run continued. |
| `blockers` | Why a real run would stop. Only a simulation gets to the end with blockers. |
| `counts` | `scanned`, `selected`, `cleared`, `would_be_cleared`, `failed`, `skipped`, `excluded`. |
| `duration_seconds` | Total duration. |
| `recap_dataset` | `null`, or `{"name", "rows_written", "error"}`. |
| `datasets` | One object per selected dataset: `name`, `type`, `connection`, `status`, `skip_code`, `detail`, `warnings`, `included_tags`, `excluded_tags`, `is_shared`, `shared_with`, `built_by_recipe`, `partition_dimensions`, `duration_seconds`. |

`is_shared` and `built_by_recipe` are `null` when the check was not possible.
