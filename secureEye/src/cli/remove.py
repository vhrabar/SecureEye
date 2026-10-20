# Remove a encoding from the models file

# Import required modules
import sys
import os
import builtins
import paths_factory

from auth import template_store
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

# Try to load the models and abort if the user does not have any yet
try:
    templates = template_store.load_all(user)
except (template_store.TemplateFileNotFound, template_store.EmptyTemplateStore):
    fail(
        "no_models",
        _("No face model known for the user {}, please run:").format(user),
        "\n\tsecureEye add\n",
    )
except template_store.TemplateSchemaError as err:
    fail(
        "model_file_invalid",
        _("The face model file {file} could not be read: {error}").format(
            file=paths_factory.user_model_path(user), error=err
        ),
    )

# Get the ID from the cli arguments
id = builtins.secureEye_args.arguments[0]

# Look up the model the user asked for
target = next((template for template in templates if str(template.id) == id), None)

# Abort if no matching id was found
if target is None:
    fail("model_not_found", _("No model with ID {id} exists for {user}").format(id=id, user=user))

# Only ask the user if there's no -y flag
if not builtins.secureEye_args.y:
    # Double check with the user
    print(
        _('This will remove the model called "{label}" for {user}').format(
            label=target.label, user=user
        )
    )
    ans = input(_("Do you want to continue [y/N]: "))

    # Abort if the answer isn't yes
    if ans.lower() != "y":
        print(_('\nInterpreting as a "NO", aborting'))
        sys.exit(1)

    # Add a padding empty  line
    print()

# Remove the entire file if this template is the only one
if len(templates) == 1:
    template_store.delete(user)
    ok(
        {"removed": target.id, "remaining": 0},
        _("Removed last model, secureEye disabled for user"),
    )
else:
    # Save everything but the removed template back to disk
    remaining = [template for template in templates if template is not target]
    template_store.save(user, remaining)

    ok({"removed": target.id, "remaining": len(remaining)}, _("Removed model {}").format(id))
