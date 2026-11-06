"""Macro "Report Dataset Tags": reports how the datasets of a project use tags. It changes nothing.

- report.py: the work. Reads the datasets, the project tag list and the tag categories, and counts.
- recap.py: what the recap holds: JSON summary, recap dataset rows, HTML page.
- macro.py: the MaintenanceMacro that ties them together for the shared runner.
"""

from dss_project_maintenance.macros.report_dataset_tags.macro import MACRO

__all__ = ["MACRO"]
