from dataclasses import dataclass


@dataclass
class MatchResult:
    model_index: int
    distance: float


@dataclass
class RuntimeStats:
    frames: int = 0
    valid_frames: int = 0
    dark_tries: int = 0
    black_tries: int = 0
    lowest_certainty: float = 10.0
