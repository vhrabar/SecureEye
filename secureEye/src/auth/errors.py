from enum import IntEnum


class ExitCode(IntEnum):
    SUCCESS = 0
    NO_FACE_MODEL = 10
    TIMEOUT_REACHED = 11
    ABORT = 12
    TOO_DARK = 13
    INVALID_DEVICE = 14
    RUBBERSTAMP = 15
