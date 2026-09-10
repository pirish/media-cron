from media_cron.metadata.base import VideoSpoolEngineProtocol
from media_cron.metadata.video_spooler import VideoSpoolEngine


def test_video_spool_engine_satisfies_protocol():
    engine = VideoSpoolEngine()
    assert isinstance(engine, VideoSpoolEngineProtocol)
    assert hasattr(engine, "stage_bundle")
    assert hasattr(engine, "promote_bundle")
    assert hasattr(engine, "execute_post_command")
    assert hasattr(engine, "spool_release")
