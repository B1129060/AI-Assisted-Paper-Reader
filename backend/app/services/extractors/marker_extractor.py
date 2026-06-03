# Marker-based PDF markdown extractor kept as an extractor implementation.

from functools import lru_cache
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.config.parser import ConfigParser

@lru_cache(maxsize=1)
# Internal helper for get marker models.
def _get_marker_models():
    config_parser = ConfigParser({})
    return create_model_dict()

# Extract markdown from a PDF using Marker.
def extract_markdown_with_marker(pdf_path: str) -> str:
    models = _get_marker_models()
    converter = PdfConverter(
        artifact_dict=models,
    )
    rendered = converter(pdf_path)
    return rendered.markdown or ""