"""The macros of the plugin: one package per macro, named after its folder in python-runnables.

Each package exposes MACRO, an instance of its MaintenanceMacro subclass. A macro imports only the
shared code (dss_maintenance.core and dss_maintenance.recap), never another macro.
"""
