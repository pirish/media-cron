from media_cron.metadata.base import MusicSpoolEngineProtocol
from media_cron.metadata.music_spooler import MusicSpoolEngine


def test_music_spool_engine_satisfies_protocol():
    engine = MusicSpoolEngine()
    assert isinstance(engine, MusicSpoolEngineProtocol)
    assert hasattr(engine, "stage_bundle")
    assert hasattr(engine, "promote_bundle")
    assert hasattr(engine, "execute_post_command")
    assert hasattr(engine, "spool_release")
