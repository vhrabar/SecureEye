# Download the data files the dlib backend needs

import dlib_models

from cli.output import fail, ok, say
from i18n import _

directory = str(dlib_models.data_dir())

if not dlib_models.missing():
    ok(
        {"fetched": [], "directory": directory},
        _("The dlib data files are already in {}").format(directory),
    )
else:
    say(_("Downloading the dlib data files to {}").format(directory))
    try:
        fetched = dlib_models.fetch(lambda name: say("  " + name))
    except (OSError, dlib_models.FetchError) as err:
        fail("fetch_failed", _("Could not download the dlib data files: {}").format(err))

    ok({"fetched": fetched, "directory": directory}, _("Done."))
