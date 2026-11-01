from enum import IntEnum


class ExitCode(IntEnum):
    SUCCESS = 0
    NO_FACE_MODEL = 10
    TIMEOUT_REACHED = 11
    ABORT = 12
    TOO_DARK = 13
    INVALID_DEVICE = 14
    RUBBERSTAMP = 15
    # The user has face models, but from a different recognizer than the one
    # configured now. They have to enroll again; nothing else will help.
    TEMPLATE_MODEL_MISMATCH = 16
