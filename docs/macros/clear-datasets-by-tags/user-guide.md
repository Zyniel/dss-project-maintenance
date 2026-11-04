# Clear Datasets by Tags: user guide

The macro clears the data of the datasets of a project, selected by their tags. The definitions, schemas and settings of the datasets stay: only the data is cleared.

You cannot undo a clear, and anything that uses a cleared dataset can break until it is rebuilt. The macro only simulates while "Simulate" is checked.

## Who can run it

The macro is in **Macros > Project maintenance** of each project, for users who can write in the project ("Write project content"). It acts with the rights of the user: it never clears a dataset that the user could not clear by hand.

Only project administrators can read which datasets are shared with other projects. See [Checks before clearing](#checks-before-clearing).

## Select the datasets

1. **Included tags:** the datasets with these tags are selected. Without included tags, all datasets of the project are selected.
2. **Excluded tags:** among them, the datasets with these tags are excluded, and never cleared. Without excluded tags, no dataset is excluded.

You need at least one tag, in one of the two lists: otherwise the macro would clear all datasets of the project.

Each list has three fields:

| Field | Content |
|---|---|
| Included Tags / Excluded Tags | Tags typed by hand, for example `temporary`. Press Enter after each one. |
| Included Cat. Tags / Excluded Cat. Tags | Category tags picked from a list: the tags of the datasets of the project, read when the form opens. DSS writes them `<category>:<value>`, for example `Stage:Raw`. A DSS administrator can limit the list to some categories, in the plugin setting "Tag categories". |
| Included tags match / Excluded tags match | "Any": a dataset matches if it has at least one tag of the list. "All": only if it has every tag of the list. |

The typed tags and the category tags of a list make one single list.

Rules:

- **Exact match**, upper and lower case included: `Temporary` does not match `temporary`.
- **A tag in both lists** is excluded, and the recap shows a notice. Check the two lists.
- **A tag on no dataset** selects nothing, or excludes nothing. It does not stop the run.

## The options

| Option | Default | Effect |
|---|---|---|
| Simulate | Checked | Only shows what would be cleared. Nothing is cleared. |
| Clear shared datasets | Checked | Checked: the projects that use them can break. Unchecked: they are skipped, which needs project admin rights. |
| Clear partitioned datasets | Unchecked | Checked: all their partitions are cleared. Unchecked: they are skipped. |
| Clear datasets with no recipe | Unchecked | Checked: no recipe can rebuild their data, so it is lost. Unchecked: they are skipped. |
| If an error occurs | Continue, run ends as success | When a dataset cannot be cleared. The other choices end the run in error: see [automation](automation.md#scenarios). |
| Write to a dataset | Unchecked | Keeps the recap in a dataset: see [automation](automation.md#summary-dataset). |
| Summary dataset | None | Visible when the option above is checked. |
| Append mode | Checked | Visible when "Write to a dataset" is checked. Unchecked: each run replaces the content of the dataset. |
| If the summary is not written | Continue | Visible when "Write to a dataset" is checked. "Fail the run" is for scenarios. |

A dataset loaded by hand, by code or by the API, like an input dataset, often has no recipe: check "Clear datasets with no recipe" to clear it.

DSS remembers the values of your last run of the macro in this project, in this browser. After a plugin update, click **Reset to default** to see the new defaults.

## Datasets that are never cleared

- **Datasets shared by other projects** into this one: they are never selected, and not shown.
- **External datasets:** DSS does not manage their data, for example a SQL table created outside DSS. They are skipped, with the reason in the recap.
- **The summary dataset** of the run.

## How the macro decides

For each selected dataset, the first rule that applies wins:

1. it has the excluded tags: **Excluded**;
2. it is the summary dataset: **Skipped**;
3. DSS does not manage it (external): **Skipped**;
4. it is shared and "Clear shared datasets" is unchecked: **Skipped**;
5. it is partitioned and "Clear partitioned datasets" is unchecked: **Skipped**;
6. no recipe builds it and "Clear datasets with no recipe" is unchecked: **Skipped**;
7. otherwise, the dataset is to clear. A simulation marks it **Cleared (Simulate)**. A real run marks it **Cleared** or **Failed**, or **Skipped** if the run stopped before it ("If an error occurs" is "Raise exception").

## Checks before clearing

The macro first decides for each dataset, and only then clears. It finds every reason to stop a real run before it clears anything. A simulation shows these reasons in a red banner, and does not stop.

| Check | When it works | When it fails |
|---|---|---|
| Datasets shared with other projects | The recap names the projects of each shared dataset. | DSS gives this list only to project administrators. With "Clear shared datasets" checked (the default), the run continues with a notice. Unchecked, a real run stops: it cannot skip what it cannot find. |
| Datasets with no recipe | The recap shows them. | Reading the Flow failed. Option unchecked: a real run stops. Checked: the run continues with a notice. |

So, with "Clear shared datasets" unchecked, a real run by an editor who is not a project administrator stops. Ask a project administrator to run it, or check "Clear shared datasets".

## Read the recap

At the top: the macro, the project, who ran it and when (UTC). Then the banners:

- **Yellow, first:** "Warning: the run went on after these errors", with the datasets that could not be cleared, or the summary dataset that was not written.
- **Yellow:** simulation, or a notice (a check that was not possible, a tag in both lists...).
- **Red:** reasons why a real run would stop.
- **Grey:** the summary dataset was written.

Then:

- **The figures:** "Cleared" and "Failed" (or "Cleared (Simulate)" in a simulation), "Skipped", "Excluded" if there are excluded tags, "Selected", "Scanned" and "Duration". Click a figure to show only these datasets in the table. "Selected" shows them all again.
- **The options** of the run.
- **The tags**, included and excluded, with "Any" or "All", and the number of datasets that have each tag. An included tag on no dataset is yellow: maybe it has a typo.
- **The table:** one row per selected dataset, failures first. In DSS, it is interactive: sort with the header of a column, filter with its menu, search all columns with the box above, and save the rows with "Export CSV". The CSV contains the status as text, without the icon.

"Download" saves the recap as an HTML file. Opened alone, it loads AG Grid from the internet to show the same interactive table. Offline, or if an administrator turned it off, it shows a simple table.

| Status | Meaning |
|---|---|
| Cleared | The data was cleared. The messages of DSS are in the Detail column. |
| Cleared (Simulate) | Simulation: nothing was cleared, a real run would clear it. |
| Failed | DSS could not clear it. The error is in the Detail column. The run continued with the next datasets, unless "If an error occurs" is "Raise exception". |
| Skipped | A rule or an option protected it, or the run stopped before it ("Not tried: the run stopped"). The reason is in the Detail column. |
| Excluded | It has the excluded tags. |

The Detail column says why: "Has included tags", "Has excluded tags", or "Has all included tags" and "Has all excluded tags" with "All". A skipped dataset says why, for example "Is external" or "Has no recipe; 'Clear datasets with no recipe' is unchecked". It also gives the warnings of cleared datasets: shared, partitioned, with no recipe, or "Sharing not checked" when the user cannot read the sharing.

## Good practice

- **Simulate first.** Read the recap, mainly the warnings and the skipped datasets, before you uncheck "Simulate".
- **Protect the summary dataset.** Give it an excluded tag, so that runs with other tags leave it alone.
- **Check the advanced options with care.** Each one lets the macro clear data that is harder to get back. "Clear shared datasets" is checked by default: uncheck it when other projects must keep their data.
- **In a scenario,** choose "Continue, run ends in error" or "Raise exception" in "If an error occurs", and "Fail the run" in "If the summary is not written" if you keep a history, so that the step turns red when something fails.
