from media_cron.config import ExternalProviderConfig
from media_cron.metadata.base import MetadataProviderProtocol, default_provider_registry
from media_cron.metadata.models import MetadataMatch


class MockTestProvider:
    @property
    def provider_name(self) -> str:
        return "mock_provider"

    def search(
        self,
        title: str,
        author: str | None = None,
        config: ExternalProviderConfig | None = None,
    ) -> list[MetadataMatch]:
        if "empty" in title.lower():
            return []
        return [
            MetadataMatch(
                title=title,
                author=author or "Mock Author",
                year=2020,
                provider="mock_provider",
                confidence=0.95,
            )
        ]


def test_mock_provider_conforms_to_protocol():
    provider = MockTestProvider()
    assert isinstance(provider, MetadataProviderProtocol)
    assert provider.provider_name == "mock_provider"

    matches = provider.search(title="Test Book", author="Test Author")
    assert len(matches) == 1
    assert matches[0].title == "Test Book"
    assert matches[0].author == "Test Author"
    assert matches[0].confidence == 0.95


def test_registry_registration_and_lookup():
    reg = default_provider_registry
    reg.register("mock_provider", MockTestProvider)

    retrieved_cls = reg.get("mock_provider")
    assert retrieved_cls == MockTestProvider

    inst = retrieved_cls()
    assert inst.provider_name == "mock_provider"
    assert "mock_provider" in reg.available_providers()
