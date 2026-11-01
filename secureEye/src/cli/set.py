# Set one or more config values
#
#   secureEye set certainty 3
#   secureEye set certainty 3 dark_threshold 60
#
# Every key is checked before anything is written, and the file is replaced in one step, so a bad pair leaves
# config.ini untouched.

# Import required modules
import builtins
import os
import shutil
import tempfile
import paths_factory

from cli.output import fail, ok
from i18n import _

# Get the absolute filepath
config_path = paths_factory.config_file_path()

arguments = builtins.secureEye_args.arguments

# Check if enough arguments have been passed
if len(arguments) < 2 or len(arguments) % 2 != 0:
    fail(
        "missing_argument",
        _("Please add a setting you would like to change and the value to set it to"),
        _("For example:"),
        "\n\tsecureEye set certainty 3\n",
    )

# Pair up the names and values from the cli
updates = dict(zip(arguments[0::2], arguments[1::2], strict=True))

# A line break would let the value write extra lines into config.ini
for set_value in updates.values():
    if "\n" in set_value or "\r" in set_value:
        fail("invalid_value", _("Config values can not contain line breaks"))

with open(config_path, encoding="utf-8") as config_file:
    lines = config_file.readlines()


def option_name(line):
    """The option a line sets, if it is one we were asked to update."""
    for set_name in updates:
        if line.startswith(set_name + " "):
            return set_name
    return None


# If we don't have the line it is not in the config file
found = {option_name(line) for line in lines} - {None}
for set_name in updates:
    if set_name not in found:
        fail("unknown_option", _('Could not find a "{}" config option to set').format(set_name))

# Update the matching lines and keep everything else, comments included, as it was
new_lines = []
for line in lines:
    set_name = option_name(line)
    new_lines.append(line if set_name is None else set_name + " = " + updates[set_name] + "\n")

# Write next to the original and swap it in, so a crash can not leave a half written file
config_dir = os.path.dirname(os.path.abspath(config_path))
with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=config_dir, delete=False) as new_file:
    new_file.writelines(new_lines)
shutil.copymode(config_path, new_file.name)
os.replace(new_file.name, config_path)

ok({"updated": updates}, _("Config option updated"))
