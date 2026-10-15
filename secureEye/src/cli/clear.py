# Clear all models by deleting the whole file

# Import required modules
import os
import sys
import builtins
import paths_factory

from cli.output import json_mode, ok
from i18n import _

# Get the passed user
user = builtins.secureEye_user

# Nothing to clear is an error for people but a no-op for the GUI, which only cares about the end state
nothing_to_clear = None

# Check if the models folder is there
if not os.path.exists(paths_factory.user_models_dir_path()):
    nothing_to_clear = _("No models created yet, can't clear them if they don't exist")

# Check if the user has a models file to delete
elif not os.path.isfile(paths_factory.user_model_path(user)):
    nothing_to_clear = _("{} has no models or they have been cleared already").format(user)

if nothing_to_clear is not None:
    if json_mode():
        ok({"cleared": False})
        sys.exit(0)
    print(nothing_to_clear)
    sys.exit(1)

# Only ask the user if there's no -y flag
if not builtins.secureEye_args.y:
    # Double check with the user
    print(_("This will clear all models for ") + user)
    ans = input(_("Do you want to continue [y/N]: "))

    # Abort if they don't answer y or Y
    if ans.lower() != "y":
        print(_('\nInterpreting as a "NO", aborting'))
        sys.exit(1)

# Delete otherwise
os.remove(paths_factory.user_model_path(user))
ok({"cleared": True}, _("\nModels cleared"))
