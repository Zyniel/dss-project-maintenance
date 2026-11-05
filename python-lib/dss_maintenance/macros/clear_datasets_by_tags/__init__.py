"""Macro "Clear Datasets by Tags": clears the data of the datasets matching the included tags and not the excluded ones.

- cleanup.py: the work. Reads the form, decides what to do with each dataset, then clears them.
- recap.py: what the recap holds: JSON summary, recap dataset rows, HTML page, failure message.
- macro.py: the MaintenanceMacro that ties them together for the shared runner.
"""

from dss_maintenance.macros.clear_datasets_by_tags.macro import MACRO

__all__ = ["MACRO"]
