from media_cron.metadata.base import default_provider_registry
from media_cron.metadata.providers.audnexus import AudnexusProvider
from media_cron.metadata.providers.openlibrary import OpenLibraryProvider

# Register default built-in providers
default_provider_registry.register("openlibrary", OpenLibraryProvider)
default_provider_registry.register("audnexus", AudnexusProvider)

__all__ = ["OpenLibraryProvider", "AudnexusProvider"]
