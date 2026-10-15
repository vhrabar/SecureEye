# Remove a encoding from the models file

# Import required modules
import sys
import os
import json
import builtins
import paths_factory

from cli.output import fail, ok
from i18n import _

user = builtins.secureEye_user

# Check if enough arguments have been passed
if not builtins.secureEye_args.arguments:
    fail(
        "missing_argument",
        _("Please add the ID of the model you want to remove as an argument"),
        _("For example:"),
        "\n\tsecureEye remove 0\n",
        _("You can find the IDs by running:"),
        "\n\tsecureEye list\n",
    )

# Check if the models file has been created yet
if not os.path.exists(paths_factory.user_models_dir_path()):
    fail(
        "models_not_initialized",
        _("Face models have not been initialized yet, please run:"),
        "\n\tsecureEye add\n",
    )

# Path to the models file
enc_file = paths_factory.user_model_path(user)

# Try to load the models file and abort if the user does not have it yet
try:
    encodings = json.load(open(enc_file))
except FileNotFoundError:
    fail(
        "no_models",
        _("No face model known for the user {}, please run:").format(user),
        "\n\tsecureEye add\n",
    )
except json.JSONDecodeError as err:
    fail(
        "model_file_invalid",
        _("The face model file {file} is not valid JSON: {error}").format(file=enc_file, error=err),
    )

# Tracks if a encoding with that id has been found
found = False

# Get the ID from the cli arguments
id = builtins.secureEye_args.arguments[0]

# Loop though all encodings and check if they match the argument
for enc in encodings:
    if str(enc["id"]) == id:
        # Only ask the user if there's no -y flag
        if not builtins.secureEye_args.y:
            # Double check with the user
            print(
                _('This will remove the model called "{label}" for {user}').format(
                    label=enc["label"], user=user
                )
            )
            ans = input(_("Do you want to continue [y/N]: "))

            # Abort if the answer isn't yes
            if ans.lower() != "y":
                print(_('\nInterpreting as a "NO", aborting'))
                sys.exit(1)

            # Add a padding empty  line
            print()

        # Mark as found and print an enter
        found = True
        removed_id = enc["id"]
        break

# Abort if no matching id was found
if not found:
    fail("model_not_found", _("No model with ID {id} exists for {user}").format(id=id, user=user))

# Remove the entire file if this encoding is the only one
if len(encodings) == 1:
    os.remove(paths_factory.user_model_path(user))
    ok(
        {"removed": removed_id, "remaining": 0},
        _("Removed last model, secureEye disabled for user"),
    )
else:
    # A place holder to contain the encodings that will remain
    new_encodings = []

    # Loop though all encodings and only add those that don't need to be removed
    for enc in encodings:
        if str(enc["id"]) != id:
            new_encodings.append(enc)

    # Save this new set to disk
    with open(enc_file, "w") as datafile:
        json.dump(new_encodings, datafile)

    ok({"removed": removed_id, "remaining": len(new_encodings)}, _("Removed model {}").format(id))
