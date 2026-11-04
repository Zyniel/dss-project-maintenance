# Admin guide

What a DSS administrator must know to install the plugin and trust it.

## Requirements

- DSS 13. Checked on DSS 13.4.4.
- The built-in Python 3.9 environment of DSS. No code environment, no extra package.

## Install and update

1. Download the zip of a version from the [Releases](https://github.com/Zyniel/dss-project-maintenance/releases) of the repository.
2. Install: **Plugins > Add plugin > Upload**. Update: **Plugins > Installed > DSS Project Maintenance**, then upload the new zip.
3. Set the [plugin settings](../README.md#plugin-settings) if needed.

After an update, DSS still shows each user the values of their last run in the form. "Reset to default" shows the new defaults.

## Rights

The macros run with the rights of the user who runs them (`"impersonate": true`). They give no extra rights.

| Macro | Who can run it | What it changes |
|---|---|---|
| Clear Datasets by Tags | Users who can write in the project | The data of the selected datasets. It cannot be undone. |
| Report Dataset Tags | Users who can read the project | Nothing. |

Some checks need more rights. Only project administrators can read which datasets are shared, and only DSS administrators can read the global tag categories. Without these rights, the recap says what was not checked.

The macros were checked on DSS as a DSS administrator only. See [verification](verification.md).

## What Clear Datasets by Tags never does

- It never clears data while "Simulate" is checked, and "Simulate" is checked by default.
- It never clears an external dataset or the summary dataset.
- It never deletes a dataset: only the data is cleared, the definition stays.

"Clear shared datasets" is checked by default: the projects that use a shared dataset can break when it is cleared.

## Network

- In DSS, nothing is loaded from the internet: the recap uses the AG Grid of DSS.
- A downloaded recap, opened outside DSS, loads AG Grid from the "AG Grid URL" setting (by default, cdn.jsdelivr.net). The browser checks the file with the integrity hash. It sends no project data. Set an internal copy, or leave the URL empty to load nothing.

## Audit

- Each run writes its whole recap on the `RECAP_JSON` line of its log.
- A user can also write the recap to a dataset of the project, in "Append mode" to keep a history.

The DSS API calls of the macros are listed in [architecture](architecture.md#the-dss-api-calls).
