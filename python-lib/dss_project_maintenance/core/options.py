"""Read the options of a macro form.

Every macro form ends with the "Summary" section. A macro that changes data also has the "Run"
section, just before it. The options of these two sections are read here.

Each section has its own choice for errors: "If an error occurs" for the work, in the "Run" section,
and "If the summary is not written" for the recap dataset, in the "Summary" section.

The form calls the recap dataset "Summary dataset". The code keeps the word recap, as in the
parameter names (recap_to_dataset, recap_dataset, recap_append, on_recap_error) that scenarios and
API calls use.
"""

from typing import Any, Optional

# The values of "If an error occurs" and "If the summary is not written". DSS shows a macro run as a
# success or a failure, never as a warning.
ON_ERROR_CONTINUE = "CONTINUE"  # Go on. The run ends as a success.
ON_ERROR_FAIL = "FAIL"  # Go on. The run ends in error.
ON_ERROR_STOP = "STOP"  # Stop at the first error. The run ends in error. Only for the work.

# The choices of "If an error occurs", in the order of the form. A macro that changes data stops its
# work at the first error when the value is ON_ERROR_STOP.
RUN_ERROR_CHOICES = {
    ON_ERROR_CONTINUE: "Continue, run ends as success",
    ON_ERROR_FAIL: "Continue, run ends in error",
    ON_ERROR_STOP: "Raise exception",
}

# The choices of "If the summary is not written". Writing the summary is the last step, so there is
# nothing left to stop.
RECAP_ERROR_CHOICES = {ON_ERROR_CONTINUE: "Continue", ON_ERROR_FAIL: "Fail the run"}

# The values that end the run in error.
FAILING_ON_ERROR = (ON_ERROR_FAIL, ON_ERROR_STOP)

# Default value and label of the options of the "Run" section, only in the forms of the macros that
# change data. A test checks each runnable.json. By default, every item is tried, and an error fails the
# run: a scenario step turns red.
RUN_OPTION_DEFAULTS: dict[str, Any] = {"on_error": ON_ERROR_FAIL}
RUN_OPTION_LABELS = {"on_error": "If an error occurs"}

# Default value and label of the options of the "Summary" section, in every macro form. A test checks
# each runnable.json.
RECAP_OPTION_DEFAULTS: dict[str, Any] = {
    "recap_to_dataset": False,
    "recap_append": True,
    "on_recap_error": ON_ERROR_CONTINUE,
}
RECAP_OPTION_LABELS = {
    "recap_to_dataset": "Write to a dataset",
    "recap_dataset": "Summary dataset",
    "recap_append": "Append mode",
    "on_recap_error": "If the summary is not written",
}


def read_checkbox(config: dict[str, Any], name: str, default: bool) -> bool:
    """Return the value of a checkbox of the form.

    Only a real true or false counts. Any other value sent through the API, such as None or the text
    "false", gives the default.
    """
    value = config.get(name, default)
    return value if isinstance(value, bool) else default


def read_choice(config: dict[str, Any], name: str, choices: dict[str, str], default: str) -> str:
    """Return the value of a select list of the form.

    A value that is not one of the choices, such as None or a label, gives the default.
    """
    value = config.get(name, default)
    return value if isinstance(value, str) and value in choices else default


def option_unchecked(label: str) -> str:
    """Return the text saying that an option of the form is unchecked."""
    return f"'{label}' is unchecked"


def read_recap_dataset_name(config: dict[str, Any], project_key: str) -> Optional[str]:
    """Return the name of the recap dataset, or None when the form does not ask for one.

    The DSS dataset picker has no empty entry, so unchecking "Write to a dataset" is how a
    user stops using a dataset picked earlier. Only a real false turns it off: an API call that gives
    just recap_dataset still gets its recap.

    :raises ValueError: if the dataset belongs to another project, or if none is picked while checked
    """
    to_dataset = config.get("recap_to_dataset")
    if to_dataset is False:
        return None
    name = str(config.get("recap_dataset") or "").strip()
    if "." in name:
        owner, _, name = name.partition(".")
        if owner != project_key:
            raise ValueError(f"The summary dataset must belong to this project, not to project {owner}.")
    if not name and to_dataset is True:
        raise ValueError(f"Pick a summary dataset, or uncheck '{RECAP_OPTION_LABELS['recap_to_dataset']}'.")
    return name or None


def read_run_options(config: dict[str, Any]) -> dict[str, Any]:
    """Return the options of the "Run" section of the form. Only for a macro that changes data."""
    return {"on_error": read_choice(config, "on_error", RUN_ERROR_CHOICES, RUN_OPTION_DEFAULTS["on_error"])}


def read_recap_options(config: dict[str, Any], project_key: str) -> dict[str, Any]:
    """Return the options of the "Summary" section of the form."""
    recap_dataset = read_recap_dataset_name(config, project_key)
    return {
        "recap_to_dataset": recap_dataset is not None,
        "recap_dataset": recap_dataset,
        "recap_append": read_checkbox(config, "recap_append", RECAP_OPTION_DEFAULTS["recap_append"]),
        "on_recap_error": read_choice(
            config, "on_recap_error", RECAP_ERROR_CHOICES, RECAP_OPTION_DEFAULTS["on_recap_error"]
        ),
    }
