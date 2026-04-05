"""
Per-group configuration for the scraper pipeline.

Each group that can be scraped is represented by a GroupConfig instance.
Scrapers are generic — they accept a GroupConfig and operate on whatever
group the config describes. Adding a new group is a config-only operation.
"""
from dataclasses import dataclass, field


@dataclass
class GroupConfig:
    # DB artist_id for the group's primary artist row (from seed migration)
    artist_id: int

    # Human-readable group name — used in Spotify/YouTube search queries
    artist_name: str

    # Wikipedia discography page URL (Phase 1)
    wikipedia_discography_url: str

    # Wikipedia songs list URL (Phase 2)
    wikipedia_songs_url: str

    # Fandom MediaWiki API base URL (Phase 3)
    fandom_api: str

    # Maps Wikipedia discography heading text → release_type column value.
    # Different groups have different heading structures on their Wikipedia pages.
    heading_to_release_type: dict[str, str]

    # Member name aliases → artist_id. Used to resolve credit cell names and
    # Fandom entry titles (e.g. "Bang Chan "Song Title"") to DB artist rows.
    member_aliases: dict[str, int] = field(default_factory=dict)

    # Lowercase member name set. Used to detect member-suffix parentheticals
    # in Spotify track titles (e.g. "Song (Bang Chan, Felix)").
    member_names: frozenset[str] = field(default_factory=frozenset)


SKZ_CONFIG = GroupConfig(
    artist_id=1,
    artist_name="Stray Kids",
    wikipedia_discography_url="https://en.wikipedia.org/wiki/Stray_Kids_discography",
    wikipedia_songs_url="https://en.wikipedia.org/wiki/List_of_songs_recorded_by_Stray_Kids",
    fandom_api="https://stray-kids.fandom.com/api.php",
    heading_to_release_type={
        "studio albums": "studio_album",
        "compilation albums": "compilation_album",
        "reissues": "repackage",
        "extended plays": "ep",
        "mixtapes": "mixtape",
        "single albums": "single_album",
        "as lead artist": "digital_single",
        "promotional singles": "digital_single",
        "other charted songs": "digital_single",
        "guest appearances": "feature",
    },
    member_aliases={
        "straykids": 1, "stray kids": 1,
        "3racha": 2, "three racha": 2,
        "danceracha": 3, "dance racha": 3,
        "vocalracha": 4, "vocal racha": 4,
        "bang chan": 5, "bangchan": 5, "chan": 5, "chris": 5, "cb97": 5,
        "lee know": 6, "leeknow": 6, "minho": 6,
        "changbin": 7, "seo changbin": 7, "spearb": 7,
        "hyunjin": 8, "hwang hyunjin": 8,
        "han": 9, "han jisung": 9, "jisung": 9, "j.one": 9,
        "felix": 10, "lee felix": 10,
        "seungmin": 11, "kim seungmin": 11,
        "i.n": 12, "in": 12, "yang jeongin": 12, "jeongin": 12,
        "woojin": 13, "kim woojin": 13,
    },
    member_names=frozenset({
        "bang chan", "lee know", "changbin", "hyunjin", "han", "felix",
        "seungmin", "i.n", "minho", "jisung", "chris",
    }),
)

GROUP_CONFIGS = {
    "skz": SKZ_CONFIG,
}
