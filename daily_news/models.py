from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Item:
    title: str
    url: str
    source: str
    category: str
    market: str = "global"
    published: str = ""
    description: str = ""
    score: float = 0.0
    title_vi: str = ""
    title_en: str = ""
    summary_vi: str = ""
    summary_en: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

