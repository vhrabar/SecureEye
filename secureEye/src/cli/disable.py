# Set the disable flag

# Import required modules
import sys
import builtins
import fileinput
import configparser
import paths_factory

from cli.output import fail, json_mode, ok
from i18n import _

# Get the absolute filepath
config_path = paths_factory.config_file_path()

# Read config from disk
config = configparser.ConfigParser()
config.read(config_path)

# Check if enough arguments have been passed
if not builtins.secureEye_args.arguments:
    fail("missing_argument", _("Please add a 0 (enable) or a 1 (disable) as an argument"))

# Get the cli argument
argument = builtins.secureEye_args.arguments[0]

# Translate the argument to the right string
if argument == "1" or argument.lower() == "true":
    out_value = "true"
elif argument == "0" or argument.lower() == "false":
    out_value = "false"
else:
    # Of it's not a 0 or a 1, it's invalid
    fail("invalid_value", _("Please only use 0 (enable) or 1 (disable) as an argument"))

# Don't do anything when the state is already the requested one. The GUI only cares about the end state.
if out_value == config.get("core", "disabled", fallback=True):
    if json_mode():
        ok({"disabled": out_value == "true", "changed": False})
        sys.exit(0)
    print(_("The disable option has already been set to ") + out_value)
    sys.exit(1)

# Loop though the config file and only replace the line containing the disable config
for line in fileinput.input([config_path], inplace=1):
    print(
        line.replace(
            "disabled = " + config.get("core", "disabled", fallback=True), "disabled = " + out_value
        ),
        end="",
    )

# Print what we just did
if out_value == "true":
    ok({"disabled": True, "changed": True}, _("SecureEye has been disabled"))
else:
    ok({"disabled": False, "changed": True}, _("SecureEye has been enabled"))
