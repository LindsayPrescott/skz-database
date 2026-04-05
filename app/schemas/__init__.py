from app.schemas import artists, collaborators, songs  # noqa: F401 — ensure all schema modules are loaded

# Resolve forward references that couldn't be resolved at class-definition time
# due to cross-module dependencies (e.g. SongCreditResponse.artist -> ArtistResponse).
songs.SongCreditResponse.model_rebuild(_types_namespace={
    "ArtistResponse": artists.ArtistResponse,
    "CollaboratorResponse": collaborators.CollaboratorResponse,
})
