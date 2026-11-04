"""The code of the DSS Project Maintenance plugin.

- core: shared by every macro. Runs a macro, reads its form, reads a project.
- recap: shared by every macro. The HTML recap and the recap dataset.
- macros: one package per macro, which imports only core and recap.

core and recap never import a macro, and a macro never imports another one: a test checks it.
Nothing here imports dataiku, so that everything can be tested without DSS.
"""
