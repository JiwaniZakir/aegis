"""Tests for SSRF-safe URL validation."""

from __future__ import annotations

import socket
from unittest.mock import patch

import pytest

from app.security.url_validator import SSRFError, validate_url

# ---------------------------------------------------------------------------
# Scheme validation
# ---------------------------------------------------------------------------


def test_https_allowed():
    """HTTPS URLs with public IPs pass validation."""
    result = validate_url("https://example.com")
    assert result == "https://example.com"


def test_http_allowed():
    """HTTP URLs with public IPs pass validation."""
    result = validate_url("http://example.com")
    assert result == "http://example.com"


def test_ftp_scheme_rejected():
    """FTP scheme is not allowed."""
    with pytest.raises(SSRFError, match="not allowed"):
        validate_url("ftp://example.com/file.txt")


def test_file_scheme_rejected():
    """file:// scheme is not allowed."""
    with pytest.raises(SSRFError, match="not allowed"):
        validate_url("file:///etc/passwd")


def test_gopher_scheme_rejected():
    """gopher:// scheme is not allowed."""
    with pytest.raises(SSRFError, match="not allowed"):
        validate_url("gopher://example.com")


def test_empty_scheme_rejected():
    """URL without scheme is rejected."""
    with pytest.raises(SSRFError, match="not allowed"):
        validate_url("example.com")


# ---------------------------------------------------------------------------
# Hostname validation
# ---------------------------------------------------------------------------


def test_no_hostname_rejected():
    """URL with no hostname is rejected."""
    with pytest.raises(SSRFError, match="no hostname"):
        validate_url("http://")


# ---------------------------------------------------------------------------
# Private/reserved IP rejection
# ---------------------------------------------------------------------------


def _make_getaddrinfo(ip: str):
    """Helper that returns a mock getaddrinfo result resolving to the given IP."""

    def mock_getaddrinfo(host, port, **kwargs):
        family = socket.AF_INET6 if ":" in ip else socket.AF_INET
        return [(family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (ip, port or 443))]

    return mock_getaddrinfo


def test_localhost_127_rejected():
    """127.0.0.1 (localhost) is blocked."""
    with (
        patch(
            "app.security.url_validator.socket.getaddrinfo",
            _make_getaddrinfo("127.0.0.1"),
        ),
        pytest.raises(SSRFError, match="blocked IP"),
    ):
        validate_url("http://localhost")


def test_10_network_rejected():
    """10.x.x.x private network is blocked."""
    with (
        patch(
            "app.security.url_validator.socket.getaddrinfo",
            _make_getaddrinfo("10.0.0.1"),
        ),
        pytest.raises(SSRFError, match="blocked IP"),
    ):
        validate_url("http://internal.example.com")


def test_172_16_network_rejected():
    """172.16.x.x private network is blocked."""
    with (
        patch(
            "app.security.url_validator.socket.getaddrinfo",
            _make_getaddrinfo("172.16.0.1"),
        ),
        pytest.raises(SSRFError, match="blocked IP"),
    ):
        validate_url("http://internal.example.com")


def test_192_168_network_rejected():
    """192.168.x.x private network is blocked."""
    with (
        patch(
            "app.security.url_validator.socket.getaddrinfo",
            _make_getaddrinfo("192.168.1.1"),
        ),
        pytest.raises(SSRFError, match="blocked IP"),
    ):
        validate_url("http://router.local")


def test_link_local_rejected():
    """169.254.x.x link-local is blocked."""
    with (
        patch(
            "app.security.url_validator.socket.getaddrinfo",
            _make_getaddrinfo("169.254.1.1"),
        ),
        pytest.raises(SSRFError, match="blocked IP"),
    ):
        validate_url("http://link-local.example.com")


def test_cloud_metadata_rejected():
    """AWS/GCP metadata endpoint 169.254.169.254 is blocked."""
    with (
        patch(
            "app.security.url_validator.socket.getaddrinfo",
            _make_getaddrinfo("169.254.169.254"),
        ),
        pytest.raises(SSRFError, match="blocked IP"),
    ):
        validate_url("http://169.254.169.254/latest/meta-data/")


def test_ipv6_loopback_rejected():
    """IPv6 loopback ::1 is blocked."""
    with (
        patch(
            "app.security.url_validator.socket.getaddrinfo",
            _make_getaddrinfo("::1"),
        ),
        pytest.raises(SSRFError, match="blocked IP"),
    ):
        validate_url("http://ipv6-loopback.example.com")


def test_ipv6_private_fc_rejected():
    """IPv6 fc00::/7 unique-local is blocked."""
    with (
        patch(
            "app.security.url_validator.socket.getaddrinfo",
            _make_getaddrinfo("fd12::1"),
        ),
        pytest.raises(SSRFError, match="blocked IP"),
    ):
        validate_url("http://ipv6-private.example.com")


def test_public_ip_allowed():
    """Public IP addresses pass validation."""
    with patch(
        "app.security.url_validator.socket.getaddrinfo",
        _make_getaddrinfo("93.184.216.34"),
    ):
        result = validate_url("http://example.com")
        assert result == "http://example.com"


# ---------------------------------------------------------------------------
# DNS resolution failure
# ---------------------------------------------------------------------------


def test_dns_failure_rejected():
    """URLs that fail DNS resolution are rejected."""

    def mock_getaddrinfo(host, port, **kwargs):
        raise socket.gaierror("Name or service not known")

    with (
        patch("app.security.url_validator.socket.getaddrinfo", mock_getaddrinfo),
        pytest.raises(SSRFError, match="DNS resolution failed"),
    ):
        validate_url("http://nonexistent.invalid")
