from pathlib import Path

from media_cron.torrent.models import PathMappingRule, TorrentClientConfig


def test_path_mapping_exact_and_nested_prefix():
    rule = PathMappingRule(
        remote_prefix="/downloads/completed",
        local_prefix="/mnt/media/downloads/completed",
    )

    # Nested file
    remote_path = "/downloads/completed/Movie.Name.2024/movie.mkv"
    expected = Path("/mnt/media/downloads/completed/Movie.Name.2024/movie.mkv")
    assert rule.translate(remote_path) == expected

    # Exact directory match
    assert rule.translate("/downloads/completed") == Path("/mnt/media/downloads/completed")
    assert rule.translate("/downloads/completed/") == Path("/mnt/media/downloads/completed")

    # Unrelated path unchanged
    unrelated = "/other/folder/file.txt"
    assert rule.translate(unrelated) == Path(unrelated)


def test_torrent_client_config_path_translations():
    rules = [
        PathMappingRule(remote_prefix="/remote/movies", local_prefix="/local/movies"),
        PathMappingRule(remote_prefix="/remote/tv", local_prefix="/local/tv"),
    ]
    cfg = TorrentClientConfig(path_mappings=rules)

    assert cfg.translate_path("/remote/movies/movie.mkv") == Path("/local/movies/movie.mkv")
    assert cfg.translate_path("/remote/tv/show.mkv") == Path("/local/tv/show.mkv")
    assert cfg.translate_path("/unmapped/path/file.txt") == Path("/unmapped/path/file.txt")
