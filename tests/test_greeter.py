"""Tests for the tracing module (kept from template)."""

from unittest.mock import patch

from tracing import configure_tracing


def test_configure_tracing_creates_provider(tmp_path: object) -> None:
    """Test that configure_tracing returns a valid TracerProvider."""
    with patch("tracing.trace"):
        provider = configure_tracing(app_name="test")
        assert provider is not None
