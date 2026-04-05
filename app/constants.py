from typing import Literal

ReleaseType = Literal[
    "studio_album", "ep", "single_album", "compilation_album",
    "repackage", "mixtape", "digital_single", "feature",
]

Market = Literal["KR", "JP", "US", "GLOBAL"]

CreditRole = Literal[
    "vocalist", "rapper", "featured", "lyricist", "composer",
    "arranger", "producer", "executive_producer",
]

ArtistType = Literal["group", "unit", "member"]

ReleaseStatus = Literal["released", "unreleased", "snippet", "stage_only", "predebut", "cover"]

Language = Literal["ko", "en", "ja", "multi", "unknown"]

ChartRegion = Literal["KR", "JP", "US", "AU", "CA", "FR", "DE", "NZ", "UK", "GLOBAL"]
