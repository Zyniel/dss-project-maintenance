# Report Dataset Tags: user guide

The macro reports how the datasets of a project use tags. It only reads: it changes nothing in the project.

## Who can run it

The macro is in **Macros > Project maintenance** of each project, for users who can read the project ("Read project content"). It acts with the rights of the user.

To write the recap to a dataset, the user must also be able to write in the project.

## What it reports

For the datasets of the project, the macro gives:

- **each tag** that a dataset has, with its category and the datasets that have it;
- **the datasets with no tag**;
- **unused tags:** tags of the project tag list that no dataset has;
- **unknown tags:** tags that look like category tags (`<category>:<value>`, for example `Stage:Raw`), but whose category or value does not exist in the tag categories of DSS. Maybe a typo.

Datasets shared by other projects into this one are not in the report.

Each row of the table has a status:

| Status | Meaning |
|---|---|
| Unknown | A dataset has this tag, but its category or its value does not exist in the tag categories of DSS. The Detail column says which. |
| Untagged | The datasets with no tag. Their row has an empty Tag column, so that no real tag can be taken for it. |
| Unused | The tag is in the project tag list, but no dataset has it. |
| Used | At least one dataset has the tag. |

Good to know:

- **The project tag list** also contains the tags of other objects of the project, such as recipes or notebooks. So an "Unused" tag can still be on a recipe.
- **The tag categories** are set by a DSS administrator, in **Administration > Settings > Global tag categories**. Only DSS administrators can read them. For other users, the macro does not check category tags: all tags in use are "Used", and the recap shows a notice.
- **A tag with no category**, like `temporary`, is never unknown.
- **The summary dataset** is a dataset of the project, so it is in the report too.

## The options

| Option | Default | Effect |
|---|---|---|
| Show unused tags | Checked | Adds the tags of the project tag list that no dataset has. |
| Aggregate by tag | Checked | Checked: one row per tag, with the names of its datasets. Unchecked: one row per tag and dataset. |
| Write to a dataset | Unchecked | Keeps the report in a dataset: see [automation](automation.md#summary-dataset). |
| Summary dataset | None | Visible when the option above is checked. |
| Append mode | Checked | Visible when "Write to a dataset" is checked. Unchecked: each run replaces the content of the dataset. |
| If the summary is not written | Continue | Visible when "Write to a dataset" is checked. "Fail the run" is for scenarios: see [automation](automation.md#scenarios). |

There is no "Simulate" option and no "Run" section: the macro changes nothing. Only the summary dataset can fail the run, with "If the summary is not written".

## Read the recap

At the top: the macro, the project, who ran it and when (UTC). Yellow banners show a summary dataset that was not written, and the notices, for example when the tag categories could not be read.

Then:

- **The figures:** "Datasets", "Tagged", "Untagged", "Tags", "Used", "Unknown" (only when the categories were read), "Unused" (only when "Show unused tags" is checked) and "Duration". Click a figure to show only these rows in the table. "Tags" shows all rows again.
- **The options** of the run.
- **The tag categories** on the datasets, with their number of tags and of datasets. A category that DSS does not know is yellow.
- **The table**, with unknown tags first. In DSS, the table is interactive: sort, filter, search, and "Export CSV".
  - "Aggregate by tag" checked: one row per tag, with its number of datasets and their names. One row with an empty Tag column gives the datasets with no tag.
  - "Aggregate by tag" unchecked: one row per tag and dataset, with the type of the dataset. An unused tag has a row with no dataset. Each dataset with no tag has a row with an empty Tag column.

## Good practice

- **Run it as a DSS administrator** to check the category tags.
- **Fix unknown tags** in the datasets, or ask a DSS administrator to add the value to the tag category.
- **Keep a history:** write the recap to a dataset with "Append mode" checked, and run the macro from a scenario, for example each week.
