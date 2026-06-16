from dataclasses import dataclass
@dataclass(frozen=True)
class Schedule:
    minutes: list[int]
    hours: list[int]
    days: list[int]
    weekdays: list[int]
