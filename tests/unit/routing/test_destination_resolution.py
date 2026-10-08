from pathlib import Path

from media_cron.models import MediaAsset, MediaCategory
from media_cron.routing.engine import MediaRoutingEngine
from media_cron.routing.models import (
    DestinationEndpointConfig,
    DestinationEndpointType,
    ResolvedMediaRoute,
    SupportedMediaType,
    TransferMode,
)


def test_resolve_library_destination_for_music(tmp_path: Path):
    dest_path = tmp_path / "music_library"
    route = ResolvedMediaRoute(
        media_type=SupportedMediaType.MUSIC,
        source_endpoints=[],
        destination_endpoint=DestinationEndpointConfig(
            type=DestinationEndpointType.LIBRARY,
            path=dest_path,
        ),
        transfer_mode=TransferMode.HARDLINK,
    )

    asset = MediaAsset(
        path=Path("/downloads/track.flac"),
        category=MediaCategory.AUDIO_MUSIC,
        raw_title="Track",
        clean_title="One More Time",
        artist="Daft Punk",
        album="Discovery",
        track_number=1,
        extension=".flac",
        file_size=1024,
    )

    engine = MediaRoutingEngine()
    resolved = engine.resolve_target_destination(asset, route)
    assert resolved == dest_path / "Music/Daft Punk/Discovery/01 - One More Time.flac"


def test_resolve_library_destination_with_custom_template(tmp_path: Path):
    dest_path = tmp_path / "books_library"
    route = ResolvedMediaRoute(
        media_type=SupportedMediaType.BOOKS,
        source_endpoints=[],
        destination_endpoint=DestinationEndpointConfig(
            type=DestinationEndpointType.LIBRARY,
            path=dest_path,
            template="EBooks/{author}/{title}/{title}.{ext}",
        ),
        transfer_mode=TransferMode.HARDLINK,
    )

    asset = MediaAsset(
        path=Path("/downloads/book.epub"),
        category=MediaCategory.BOOK_EBOOK,
        raw_title="Dune",
        clean_title="Dune",
        author="Frank Herbert",
        extension=".epub",
        file_size=2048,
    )

    engine = MediaRoutingEngine()
    resolved = engine.resolve_target_destination(asset, route)
    assert resolved == dest_path / "EBooks/Frank Herbert/Dune/Dune.epub"


def test_resolve_spool_destination(tmp_path: Path):
    spool_path = tmp_path / "spool_movies"
    route = ResolvedMediaRoute(
        media_type=SupportedMediaType.MOVIES,
        source_endpoints=[],
        destination_endpoint=DestinationEndpointConfig(
            type=DestinationEndpointType.SPOOL,
            path=spool_path,
        ),
        transfer_mode=TransferMode.MOVE,
    )

    asset = MediaAsset(
        path=Path("/downloads/Movie.Release.2023/movie.mkv"),
        category=MediaCategory.VIDEO_MOVIE,
        raw_title="movie",
        clean_title="Movie Release",
        extension=".mkv",
        file_size=5000,
    )

    engine = MediaRoutingEngine()
    resolved = engine.resolve_target_destination(asset, route)
    assert resolved == spool_path / "Movie.Release.2023/movie.mkv"
