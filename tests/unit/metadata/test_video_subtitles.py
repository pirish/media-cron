from pathlib import Path

import pytest

from media_cron.models import DiscoveredItem
from media_cron.plugins.lookup.video import SceneVideoLookup


@pytest.fixture
def video_lookup() -> SceneVideoLookup:
    return SceneVideoLookup()


def test_find_adjacent_subtitles_with_tags(tmp_path: Path, video_lookup: SceneVideoLookup):
    video_file = tmp_path / "Dune.Part.Two.2024.2160p.mkv"
    video_file.write_bytes(b"dummy video")
    sub_en = tmp_path / "Dune.Part.Two.2024.2160p.en.srt"
    sub_en.write_text("sub en")
    sub_forced = tmp_path / "Dune.Part.Two.2024.2160p.en.forced.srt"
    sub_forced.write_text("sub forced")
    sub_sdh = tmp_path / "Dune.Part.Two.2024.2160p.sdh.vtt"
    sub_sdh.write_text("sub sdh")

    item = DiscoveredItem(
        source_path=video_file,
        file_size=video_file.stat().st_size,
        modified_time=video_file.stat().st_mtime,
        is_archive=False,
        is_directory=False,
    )
    asset = video_lookup.enrich(item)

    assert len(asset.subtitle_files) == 3
    sub_names = [p.name for p in asset.subtitle_files]
    assert sub_en.name in sub_names
    assert sub_forced.name in sub_names
    assert sub_sdh.name in sub_names


def test_find_subtitles_in_subs_subdirectory(tmp_path: Path, video_lookup: SceneVideoLookup):
    video_file = tmp_path / "Oppenheimer.2023.1080p.mkv"
    video_file.write_bytes(b"dummy video")
    subs_dir = tmp_path / "Subs"
    subs_dir.mkdir()
    sub1 = subs_dir / "2_English.srt"
    sub1.write_text("subs 1")
    sub2 = subs_dir / "3_Spanish.srt"
    sub2.write_text("subs 2")

    item = DiscoveredItem(
        source_path=video_file,
        file_size=video_file.stat().st_size,
        modified_time=video_file.stat().st_mtime,
        is_archive=False,
        is_directory=False,
    )
    asset = video_lookup.enrich(item)

    assert len(asset.subtitle_files) == 2
    assert sub1 in asset.subtitle_files
    assert sub2 in asset.subtitle_files


def test_format_sidecar_subtitle_name(video_lookup: SceneVideoLookup):
    base_dest = Path("/dest/Movies/Dune Part Two (2024)/Dune Part Two (2024) [2160p].mkv")

    # Plain untagged subtitle
    sub_plain = Path("/staging/Dune.Part.Two.2024.2160p.srt")
    assert video_lookup.format_subtitle_destination(base_dest, sub_plain) == Path(
        "/dest/Movies/Dune Part Two (2024)/Dune Part Two (2024) [2160p].srt"
    )

    # Language tag
    sub_en = Path("/staging/Dune.Part.Two.2024.2160p.en.srt")
    assert video_lookup.format_subtitle_destination(base_dest, sub_en) == Path(
        "/dest/Movies/Dune Part Two (2024)/Dune Part Two (2024) [2160p].en.srt"
    )

    # Modifier tag
    sub_forced = Path("/staging/Dune.Part.Two.2024.2160p.en.forced.srt")
    assert video_lookup.format_subtitle_destination(base_dest, sub_forced) == Path(
        "/dest/Movies/Dune Part Two (2024)/Dune Part Two (2024) [2160p].en.forced.srt"
    )

    # SDH modifier tag
    sub_sdh = Path("/staging/Dune.Part.Two.2024.2160p.sdh.vtt")
    assert video_lookup.format_subtitle_destination(base_dest, sub_sdh) == Path(
        "/dest/Movies/Dune Part Two (2024)/Dune Part Two (2024) [2160p].sdh.vtt"
    )
