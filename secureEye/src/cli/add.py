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

detector = load_detector(config)

user = builtins.secureEye_user
# The embedding space the new model will be tagged with
model_id = template_store.active_model_id(config)

ensure_models_dir()

# To try read premade templates if they exist
try:
    templates = template_store.load_all(user)
except (template_store.TemplateFileNotFound, template_store.EmptyTemplateStore):
    templates = []
except template_store.TemplateSchemaError as exc:
    print(_("Existing face models are unreadable, refusing to overwrite them: ") + str(exc))
    sys.exit(1)

# Print a warning if too many encodings are being added
if len(templates) > 3:
    print(_("NOTICE: Each additional model slows down the face recognition engine slightly"))
    print(_("Press Ctrl+C to cancel\n"))

# Make clear what we are doing if not human
if not builtins.secureEye_args.plain:
    print(_("Adding face model for the user ") + user)

# some id's can be skipped, but the last id is always the maximum
next_id = template_store.next_id(templates)

# Get the label from the cli arguments if provided
if builtins.secureEye_args.arguments:
    label = builtins.secureEye_args.arguments[0]

# Or set the default label
else:
    label = _("Model #") + str(next_id)

label = ask_label(label)

face_encoding = capture_encoding(config, detector)

# Save the new template to disk, tagged with the space that produced it
template_store.append(
    user,
    model_id=model_id,
    label=label,
    embeddings=face_encoding,
)

# Give let the user know how it went
print(
    _("""\nScan complete
Added a new model to """)
    + user
)
