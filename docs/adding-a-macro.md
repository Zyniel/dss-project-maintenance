# Add a macro

The steps, in order. The example adds a macro `drop-old-partitions` ("Drop Old Partitions").

Before you start, read the [architecture](architecture.md). To see what a macro must provide at the minimum, read `tests/support/sample_macro.py`. For complete examples, read `python-lib/dss_project_maintenance/macros/clear_datasets_by_tags` (a macro that changes data) and `python-lib/dss_project_maintenance/macros/report_dataset_tags` (a macro that only reads).

## 1. Choose the id

- **Id of the macro:** lowercase letters and dashes, for example `drop-old-partitions`. It is the name of its folder in `python-runnables`. Do not change it later: scenarios and the API use it.
- **Name of the Python package:** the same with underscores: `drop_old_partitions`.

## 2. The code of the macro

Create `python-lib/dss_project_maintenance/macros/drop_old_partitions/` with:

| File | Content |
|---|---|
| `__init__.py` | A docstring that presents the macro, then `from dss_project_maintenance.macros.drop_old_partitions.macro import MACRO`. |
| `macro.py` | The subclass of `MaintenanceMacro`, with `id`, `label`, `recap_columns`, and an instance `MACRO`. Each method calls a function of the two next files. |
| A file for the work, for example `partitions.py` | Read the form, decide, then act. |
| `recap.py` | The JSON of the recap, the rows of the summary dataset, the `RecapPage`, and `describe_failures()`: what failed in the work, as counts. |

Rules:

- **Use the shared code:** `core/options.py` to read the form, `core/project.py` to read the project, `core/tags.py` to select datasets by tags, `recap/page.py` to describe the recap.
- **Never import another macro.** If code of another macro is useful, move it to `core` or `recap`, with its tests.
- **Simulate by default.** A macro that changes data simulates by default ("Simulate" checked). Choose the default of each other option with care: an API call that sends no value gets it. A macro that only reads has no "Simulate" option.
- **Stop at the first error when asked.** When `options["on_error"]` is `ON_ERROR_STOP` ("Raise exception"), stop the work at the first failure, and mark the items not tried. The runner then ends the run in error.
- **Decide before you act.** Find all the reasons to stop before you change anything, then raise `RunStopped` if needed.
- **Report, do not crash.** A failure on one item goes into the recap, and the run continues with the next items. When the run goes on, show the failure in a banner: DSS shows a success.
- **Count, do not list.** A banner gives counts for what the summary dataset holds, and details only for what it cannot give, such as an error of DSS (use `dss_said()`) or a tag of the form. A message must not grow with the project.
- **Absolute imports:** `from dss_project_maintenance.core.tags import matches`.

## 3. The form

Create `python-runnables/drop-old-partitions/runnable.json`. The easiest way: copy the one of `clear-datasets-by-tags`, then change it.

- `meta.label`: the same as `label` in `macro.py`.
- `meta.category`: `"Project maintenance"`, to be in the same section as the other macros.
- `impersonate`: `true`. `resultType`: `"HTML"`. `macroRoles`: `[{"type": "PROJECT_MACROS"}]`.
- `permissions`: `["WRITE_CONF"]` for a macro that changes data, `["READ_CONF"]` for a macro that only reads.
- The parameters of the macro first.
- Then, at the end, the sections below, **copied with no change**:
  - for a macro that changes data only: the "Run" section, with `on_error`. Change only the descriptions of the section and of `on_error`, to say which errors your macro can have;
  - for every macro: the "Summary" section, with `recap_to_dataset`, `recap_dataset`, `recap_append`, `on_recap_error`.
- A macro that only reads, like a report, has no "Run" section. Only its summary dataset can fail the run, with `on_recap_error`.
- Each list (`STRINGS`, `MULTISELECT`) has its own `"defaultValue": []`.
- For lists of category tags, add `"paramsPythonSetup": "tag_choices.py"`.

## 4. The entry point

Copy `python-runnables/clear-datasets-by-tags/runnable.py` into `python-runnables/drop-old-partitions/`. Change only:

- the docstring;
- the import: `from dss_project_maintenance.macros.drop_old_partitions import MACRO`;
- the name of the class, for example `DropOldPartitions`.

## 5. The tests

1. Run `uv run pytest tests/plugin`. These tests already check the form, `runnable.py`, the import rules and the zip of the new macro.
2. Create `tests/macros/drop_old_partitions/` and test:
   - the work of the macro, with the fake objects of `tests/support/fakes.py`;
   - its options and their default values;
   - its recap;
   - its form (order of the parameters, default values and labels equal to the code);
   - its `runnable.py`, with `tests/support/dataiku_stub.py`.
3. If the macro needs a fake DSS object that does not exist yet, add it to `tests/support/fakes.py`.

## 6. The documentation

1. Create `docs/macros/drop-old-partitions/user-guide.md` (for users) and, if the macro runs in scenarios, `automation.md`.
2. Add the macro to the "The macros" table of the [README](../README.md).
3. Describe the new macro in the [CHANGELOG](../CHANGELOG.md).

## 7. The check on DSS

1. Build the zip and install it on a test DSS.
2. Check that the macro is in the **Project maintenance** section.
3. Run it as a simulation, then for real, on a test project.
4. Write the results in [verification](verification.md).
