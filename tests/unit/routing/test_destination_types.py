from pathlib import Path

from media_cron.models import MediaAsset, MediaCategory, TransferMode
from media_cron.routing.engine import MediaRoutingEngine
from media_cron.routing.models import (
    DestinationEndpointConfig,
    DestinationEndpointType,
    ResolvedMediaRoute,
    SupportedMediaType,
)


def test_spool_destination_preserves_release_structure(tmp_path: Path):
    spool_root = tmp_path / "spool_incoming"
    spool_root.mkdir()

    release_dir = tmp_path / "incoming" / "Inception.2010.1080p"
    file_path = release_dir / "inception.mkv"

    asset = MediaAsset(
        path=file_path,
        category=MediaCategory.VIDEO_MOVIE,
        raw_title="Inception.2010.1080p",
        clean_title="Inception",
        extension=".mkv",
        file_size=1000,
        year=2010,
    )

    route = ResolvedMediaRoute(
        media_type=SupportedMediaType.MOVIES,
        source_endpoints=[],
        destination_endpoint=DestinationEndpointConfig(
            type=DestinationEndpointType.SPOOL,
            path=spool_root,
        ),
        transfer_mode=TransferMode.COPY,
    )

    engine = MediaRoutingEngine()
    dest = engine.resolve_target_destination(asset, route)

    # In spool mode, it should be deposited under release directory without library reformatting
    expected = spool_root / "Inception.2010.1080p" / "inception.mkv"
    assert dest == expected


def test_library_destination_applies_library_formatting(tmp_path: Path):
    lib_root = tmp_path / "library"
    lib_root.mkdir()

    file_path = tmp_path / "incoming" / "Daft_Punk_Discovery" / "track1.flac"

    asset = MediaAsset(
        path=file_path,
        category=MediaCategory.AUDIO_MUSIC,
        raw_title="01 - One More Time",
        clean_title="One More Time",
        extension=".flac",
        file_size=1000,
        artist="Daft Punk",
        album="Discovery",
        track_number=1,
    )

    route = ResolvedMediaRoute(
        media_type=SupportedMediaType.MUSIC,
        source_endpoints=[],
        destination_endpoint=DestinationEndpointConfig(
            type=DestinationEndpointType.LIBRARY,
            path=lib_root,
        ),
        transfer_mode=TransferMode.COPY,
    )

    engine = MediaRoutingEngine()
    dest = engine.resolve_target_destination(asset, route)

    # In library mode, it formats using the structured template
    expected = lib_root / "Music" / "Daft Punk" / "Discovery" / "01 - One More Time.flac"
    assert dest == expected


def test_independent_spool_and_library_routes_coexist(tmp_path: Path):
    spool_root = tmp_path / "spool"
    lib_root = tmp_path / "lib"
    spool_root.mkdir()
    lib_root.mkdir()

    movie_asset = MediaAsset(
        path=tmp_path / "downloads" / "Movie.2023" / "movie.mkv",
        category=MediaCategory.VIDEO_MOVIE,
        raw_title="Movie.2023",
        clean_title="Movie",
        extension=".mkv",
        file_size=2000,
        year=2023,
    )
    music_asset = MediaAsset(
        path=tmp_path / "downloads" / "Band - Album" / "song.flac",
        category=MediaCategory.AUDIO_MUSIC,
        raw_title="song",
        clean_title="Song",
        extension=".flac",
        file_size=500,
        artist="Band",
        album="Album",
        track_number=2,
    )

    movie_route = ResolvedMediaRoute(
        media_type=SupportedMediaType.MOVIES,
        source_endpoints=[],
        destination_endpoint=DestinationEndpointConfig(
            type=DestinationEndpointType.SPOOL,
            path=spool_root,
        ),
        transfer_mode=TransferMode.COPY,
    )
    music_route = ResolvedMediaRoute(
        media_type=SupportedMediaType.MUSIC,
        source_endpoints=[],
        destination_endpoint=DestinationEndpointConfig(
            type=DestinationEndpointType.LIBRARY,
            path=lib_root,
        ),
        transfer_mode=TransferMode.COPY,
    )

    engine = MediaRoutingEngine()
    movie_dest = engine.resolve_target_destination(movie_asset, movie_route)
    music_dest = engine.resolve_target_destination(music_asset, music_route)

    assert movie_dest == spool_root / "Movie.2023" / "movie.mkv"
    assert music_dest == lib_root / "Music" / "Band" / "Album" / "02 - Song.flac"
