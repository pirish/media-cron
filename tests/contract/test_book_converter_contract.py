from media_cron.metadata.converter import (
    BookConverterProtocol,
    CalibreConverter,
    ConversionFailedError,
    ConversionTimeoutError,
    ConverterError,
    ConverterUnavailableError,
    PythonFallbackConverter,
)
from media_cron.metadata.models import BookFormat


def test_converters_conform_to_protocol():
    calibre = CalibreConverter()
    fallback = PythonFallbackConverter()

    assert isinstance(calibre, BookConverterProtocol)
    assert isinstance(fallback, BookConverterProtocol)


def test_converter_exceptions_hierarchy():
    assert issubclass(ConverterUnavailableError, ConverterError)
    assert issubclass(ConversionFailedError, ConverterError)
    assert issubclass(ConversionTimeoutError, ConverterError)


def test_converter_format_support():
    fallback = PythonFallbackConverter()
    assert fallback.supports_format(BookFormat.TXT)
    assert fallback.supports_format(BookFormat.FB2)
    assert not fallback.supports_format(BookFormat.PDF)

    calibre = CalibreConverter()
    assert calibre.supports_format(BookFormat.MOBI)
    assert calibre.supports_format(BookFormat.AZW3)
    assert calibre.supports_format(BookFormat.PDF)
    assert calibre.supports_format(BookFormat.TXT)
    assert calibre.supports_format(BookFormat.FB2)
