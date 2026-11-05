# Changelog

The changes of each version of the plugin, the most recent first.

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
