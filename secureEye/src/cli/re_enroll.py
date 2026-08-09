import builtins
import configparser
import sys

import paths_factory
from auth import template_store
from cli.enrollment import ask_label, capture_encoding, ensure_models_dir, load_detector
from i18n import _

# Read config from disk
config = configparser.ConfigParser()
config.read(paths_factory.config_file_path())

user = builtins.secureEye_user
# The embedding space the regenerated model will live in
model_id = template_store.active_model_id(config)

# Try to read the existing templates; there is nothing to regenerate without them
try:
    templates = template_store.load_all(user)
except (template_store.TemplateFileNotFound, template_store.EmptyTemplateStore):
    print(_("No face model known for the user {}, please run:").format(user))
    print("\n\tsudo secureEye -U " + user + " add\n")
    sys.exit(1)
except template_store.TemplateSchemaError as exc:
    print(_("Face models could not be read: ") + str(exc))
    sys.exit(1)

# Models in other embedding spaces survive: they are the rollback path if the
# active recognizer is switched back
stale = [template for template in templates if template.model_id == model_id]

if not builtins.secureEye_args.plain:
    print(_("Regenerating face models for {user} under {model}").format(user=user, model=model_id))

# Warn before throwing away usable models
if stale and not builtins.secureEye_args.y:
    print(
        _("This will replace {count} existing face model(s) for {user}").format(
            count=len(stale), user=user
        )
    )
    ans = input(_("Do you want to continue [y/N]: "))

    # Abort if the answer isn't yes
    if ans.lower() != "y":
        print(_('\nInterpreting as a "NO", aborting'))
        sys.exit(1)

    # Add a padding empty line
    print()

detector = load_detector(config)

ensure_models_dir()

label = ask_label(_("Model #") + str(template_store.next_id(templates)))

face_encoding = capture_encoding(config, detector)

# Only the models of the active space are replaced; the rest survive untouched
template_store.replace_space(
    user,
    model_id=model_id,
    label=label,
    embeddings=face_encoding,
)

print(
    _("""\nScan complete
Re-enrolled """)
    + user
)
