# Set a config value

# Import required modules
import builtins
import fileinput
import paths_factory

from cli.output import fail, ok
from i18n import _

# Get the absolute filepath
config_path = paths_factory.config_file_path()

# Check if enough arguments have been passed
if len(builtins.secureEye_args.arguments) < 2:
    fail(
        "missing_argument",
        _("Please add a setting you would like to change and the value to set it to"),
        _("For example:"),
        "\n\tsecureEye set certainty 3\n",
    )

# Get the name and value from the cli
set_name = builtins.secureEye_args.arguments[0]
set_value = builtins.secureEye_args.arguments[1]

# A line break would let the value write extra lines into config.ini
if "\n" in set_value or "\r" in set_value:
    fail("invalid_value", _("Config values can not contain line breaks"))

# Will be filled with the correctly config line to update
found_line = ""

# Loop through all lines in the config file
for line in fileinput.input([config_path]):
    # Save the line if it starts with the requested config option
    if line.startswith(set_name + " "):
        found_line = line

# If we don't have the line it is not in the config file
if not found_line:
    fail("unknown_option", _('Could not find a "{}" config option to set').format(set_name))

# Go through the file again and update the correct line
for line in fileinput.input([config_path], inplace=1):
    print(line.replace(found_line, set_name + " = " + set_value + "\n"), end="")

ok({"key": set_name, "value": set_value}, _("Config option updated"))
