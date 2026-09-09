from media_cron.metadata.models import UDCClassification
from media_cron.metadata.udc import UDCResolver, UDCResolverProtocol


def test_udc_resolver_conforms_to_protocol():
    resolver = UDCResolver()
    assert isinstance(resolver, UDCResolverProtocol)


def test_udc_resolver_resolve_contract():
    resolver = UDCResolver()
    # Direct match returns UDCClassification
    result = resolver.resolve(subjects=["Science Fiction"])
    assert result is not None
    assert isinstance(result, UDCClassification)
    assert result.notation == "82-311.9"
    assert "Science fiction" in result.description
    assert result.confidence >= 0.70

    # Unmatched returns None gracefully without exception
    none_result = resolver.resolve(subjects=["Random Unknown Subjectxyz123"])
    assert none_result is None
