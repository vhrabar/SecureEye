# List all models for a user

# Import required modules
import sys
import os
import time
import builtins
import paths_factory

from auth import template_store
from cli.output import fail, json_mode, ok
from i18n import _

user = builtins.secureEye_user

# Check if the models file has been created yet
if not os.path.exists(paths_factory.user_models_dir_path()):
    # Having no models is a normal state for the GUI, not an error
    if json_mode():
        ok({"user": user, "models": []})
        sys.exit(0)
    print(_("Face models have not been initialized yet, please run:"))
    print("\n\tsudo secureEye -U " + user + " add\n")
    sys.exit(1)

# Try to load the models and abort if the user does not have any yet
try:
    templates = template_store.load_all(user)
except (template_store.TemplateFileNotFound, template_store.EmptyTemplateStore):
    if json_mode():
        ok({"user": user, "models": []})
        sys.exit(0)
    if not builtins.secureEye_args.plain:
        print(_("No face model known for the user {}, please run:").format(user))
        print("\n\tsudo secureEye -U " + user + " add\n")
    sys.exit(1)
except template_store.TemplateSchemaError as err:
    fail(
        "model_file_invalid",
        _("The face model file {file} could not be read: {error}").format(
            file=paths_factory.user_model_path(user), error=err
        ),
    )

if json_mode():
    ok(
        {
            "user": user,
            "models": [
                {
                    "id": template.id,
                    "label": template.label,
                    "time": template.created,
                    "encodings": len(template.embeddings),
                    "model_id": template.model_id,
                }
                for template in templates
            ],
        }
    )
    sys.exit(0)

# Print a header if we're not in plain mode
if not builtins.secureEye_args.plain:
    print(_("Known face models for {}:").format(user))
    print("\n\033[1;29m" + _("ID  Date                 Label\033[0m"))

# Loop through all templates and print info about them
for template in templates:
    # Start with the id
    print(str(template.id), end="")

    # Add comma for machine reading
    if builtins.secureEye_args.plain:
        print(",", end="")
    # Print padding spaces after the id for a nice layout
    else:
        print((4 - len(str(template.id))) * " ", end="")

    # Format the time as ISO in the local timezone
    print(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(template.created)), end="")

    # Separate with commas again for machines, spaces otherwise
    print("," if builtins.secureEye_args.plain else "  ", end="")

    # End with the label
    print(template.label)

# Add a closing enter
print()
