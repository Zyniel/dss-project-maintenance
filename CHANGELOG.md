# Changelog

The changes of each version of the plugin, the most recent first.

## 2.1.0 - 2026-11-13

The first stable version of 2.x. 2.0.0-beta and 2.0.4-beta were pre-releases: 2.1.0 has all their changes, and no other change in the plugin.

### Update from 1.x

The changes since 1.0.2 are in 2.0.0-beta and 2.0.4-beta, below. Three of them can change the result of a scenario or a script:

- Clear Datasets by Tags refuses a run with excluded tags only, and clears nothing. In 1.x, it selected every dataset of the project. To get the same result, choose "All datasets" in "Include" (`"included_scope": "ALL_DATASETS"`).
- "If an error occurs" is "Continue, run ends in error" by default. When a dataset cannot be cleared, the run still tries every dataset, then ends in error: a scenario step turns red. To keep the 1.x behavior, choose "Continue, run ends as success" (`"on_error": "CONTINUE"`).
- The messages at the top of the recap have new texts, and so do the `notices`, `blockers` and `problems` fields of the JSON recap. Check any script that reads these texts.

After the update, the form still shows each user the values of their last run. "Reset to default" shows the new defaults.

## 2.0.4-beta - 2026-11-06

Pre-release. The changes since 2.0.0-beta.

### Clear Datasets by Tags

- New banner: how many datasets to clear carry a risk (shared, partitioned, with no recipe). In a simulation, the top of the recap now says it before you decide.
- New banner: no dataset selected, or tags on no dataset, with these tags. An excluded tag on no dataset said nothing before: with a typo in it, the datasets it should protect are cleared.
- The count of a run stopped by "Raise exception" is right: "1 of 250 datasets failed, 249 not tried", not "1 of 1 dataset".
- The Detail column no longer repeats "Sharing not checked" on each dataset: a banner says it once. The summary dataset and the JSON recap keep it.

### Every macro

- Every message at the top of the recap has the same format: a short title in bold, then what it means and what to do. A message gives counts for what the summary dataset holds, and details only for what it cannot give, such as an error of DSS or a tag of the form. So failures no longer list dataset names, and the length of a message does not depend on the number of datasets. The text of the `notices`, `blockers` and `problems` fields of the JSON recap changes with them.
- Banners are always in the same order, by colour: blue (a simulation), red (data failed, or a real run would stop), yellow (what to check), grey (for information). Failed datasets are red even when the run goes on.
- The message of a failed run says where the details are: the summary dataset if it was written, else the run log.
- An error of DSS is cut after 200 characters in a message. The log has the whole error.

### For developers

- The package in `python-lib` is renamed from `dss_maintenance` to `dss_project_maintenance`. Imports use the new name.
- `notices` is now a list of `Banner`, which has no `items` any more. A macro shows its own failures in a banner: see [adding a macro](docs/adding-a-macro.md).

## 2.0.0-beta - 2026-11-06

Pre-release.

### Clear Datasets by Tags

- **Breaking:** a run with excluded tags only is refused, and clears nothing. In 1.x, it selected every dataset of the project. To get the same result, choose "All datasets" in "Include" (`"included_scope": "ALL_DATASETS"` from the API or a scenario).
- **Breaking:** "If an error occurs" is "Continue, run ends in error" by default. A run where a dataset cannot be cleared still tries every dataset, then ends in error: a scenario step turns red, and DSS shows only the message. A missing or unknown `on_error` is now `"FAIL"`. To keep the 1.x behavior, choose "Continue, run ends as success" (`"on_error": "CONTINUE"`). The form still shows the values of your last run: "Reset to default" shows the new default.
- New first field, **Include**: "Datasets with the included tags" (default) or "All datasets". "All datasets" selects every dataset of the project, with or without excluded tags. The options and the datasets that are never cleared still apply. See the table of the [user guide](docs/macros/clear-datasets-by-tags/user-guide.md#select-the-datasets).
- With "All datasets", the form hides the included tags. Their values are ignored, and a notice names them.
- The error "Give at least one included or excluded tag" becomes "Give at least one included tag, or choose 'All datasets' in 'Include'".
- The JSON recap has the field `included_scope`. The summary dataset keeps its columns.

### Every macro

- Each notice of the recap is a banner of its own, aligned with the other banners. Before, the notices were a bulleted list with no title, shifted to the right.

### For developers

- A visibility condition of a form can also be `model.<select list> != '<choice>'`. A test checks that the parameter and the choice exist.
- Integration tests of "All datasets". They pass on DSS 13.4.4 without a license; the tests of the editor, of the reader and of scenarios need one: see [integration tests](docs/integration-tests.md).

## 1.0.2 - 2026-11-05

No change in the plugin.

- The history of the repository is one commit again: the earlier commits, with their e-mail addresses and co-author lines, are gone from `main`.
- The pre-release `1.0.0-beta` is withdrawn: its tag and its GitHub release are deleted.
- `.gitignore` also ignores `.env`.

## 1.0.1 - 2026-11-05

The changes since 1.0.0, which was released as the pre-release `1.0.0-beta`.

### Plugin

- Released under [The Unlicense](LICENSE): the plugin is in the public domain, and anyone may use it for any purpose. The zip contains the `LICENSE` file.
- A guide for DSS administrators: [admin guide](docs/admin-guide.md).

### Clear Datasets by Tags

- In a simulation, the status "Would be cleared" is now "Cleared (Simulate)", in the table, the figures and the banner. Its code stays `WOULD_BE_CLEARED`, in the JSON recap and in the summary dataset.
- In the log, the decision for each dataset says "To clear" instead of "Would be cleared", and the line of totals only gives the statuses the run can have.

### For developers

- Integration tests that run the macros on a real DSS, in `tests/integration`. They are skipped without a config file: see [integration tests](docs/integration-tests.md).
- Commits use the GitHub noreply address of each developer: see [development](docs/development.md). `.claude/settings.json` stops Claude Code from adding attribution lines to commits and pull requests.

## 1.0.0 - 2026-11-04

First version of **DSS Project Maintenance**, released as the pre-release `1.0.0-beta`.

### Plugin

- Id `project-maintenance`, name "DSS Project Maintenance". Works with DSS 13 and later, in the built-in Python 3.9 environment.
- The macros are in the **Project maintenance** section of the Macros page of a project.
- Plugin settings:
  - **AG Grid URL** and **AG Grid integrity hash**: the AG Grid that downloaded recaps load. Several hashes, separated by spaces, are accepted.
  - **Tag categories**: the "Cat. Tags" lists of the forms offer only the tags of these categories. An entry such as `Stage:` or `Stage:Raw` means `Stage`. Empty: all categories.

### Clear Datasets by Tags

- Clears the data of the datasets selected by included tags and excluded tags. Each list takes tags typed by hand and category tags picked from a list, and matches "Any" (at least one tag) or "All" (every tag).
- "Simulate" is checked by default: nothing is cleared until it is unchecked.
- Advanced options: "Clear shared datasets" (checked), "Clear partitioned datasets" and "Clear datasets with no recipe" (unchecked). When the user cannot read the sharing, each dataset cleared gets the warning "Sharing not checked".
- External datasets and the summary dataset are never cleared.
- "If an error occurs", in the "Run" section: "Continue, run ends as success" (default), "Continue, run ends in error", or "Raise exception", which stops at the first dataset that cannot be cleared.
- Project editors can run it (`WRITE_CONF`).

### Report Dataset Tags

- Reports how the datasets of a project use tags, and changes nothing: each tag with its category and its datasets, the datasets with no tag, unused tags of the project tag list, and unknown category tags (only checked for DSS administrators).
- "Show unused tags" and "Aggregate by tag" (one row per tag, or one row per tag and dataset) are checked by default.
- Project readers can run it (`READ_CONF`).

### Every macro

- An HTML recap: banners, figures, options, and an interactive table in DSS (sort, filters, search, CSV export, status icons). Downloaded and opened alone, it loads AG Grid Community to show the same table.
- Each run has an outcome, `SUCCESS`, `WARNING` or `FAILED`, shown in a banner at the top of the recap. DSS cannot show a macro run as a warning.
- The recap as JSON, in a hidden block of the HTML and on the `RECAP_JSON` line of the log.
- The "Summary" section: "Write to a dataset", "Summary dataset", "Append mode" (with the append mode of DSS), and "If the summary is not written": "Continue" or "Fail the run".

### For developers

- The shared code (`core`, `recap`) is separate from the code of each macro (`macros/<macro>`). A test checks the import rules.
- Each macro describes its recap (`RecapPage`): the shared code lays it out.
- The tests are in folders: `tests/core`, `tests/recap`, `tests/macros/<macro>`, `tests/plugin`. The tests of `tests/plugin` run on each macro.
- Checked on DSS 13.4.4: see [verification](docs/verification.md).
