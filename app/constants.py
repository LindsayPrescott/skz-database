from typing import Literal

ReleaseType = Literal[
    "studio_album", "ep", "single_album", "compilation_album",
    "repackage", "mixtape", "digital_single", "feature",
    "skz_record", "skz_player",
]

Market = Literal["KR", "JP", "US", "GLOBAL"]

CreditRole = Literal[
    "vocalist", "rapper", "featured", "lyricist", "composer",
    "arranger", "producer", "executive_producer",
]

ArtistType = Literal["group", "unit", "member"]

ReleaseStatus = Literal["released", "unreleased", "snippet", "stage_only", "predebut", "cover"]

Language = Literal["ko", "en", "ja", "multi", "unknown"]
