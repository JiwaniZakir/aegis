"""SSRF-safe URL validation — rejects private/reserved IPs and non-HTTP schemes."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

import structlog

logger = structlog.get_logger()

# Private and reserved networks that must be blocked to prevent SSRF.
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("192.88.99.0/24"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("255.255.255.255/32"),
    # IPv6 private/reserved ranges
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("ff00::/8"),
    ipaddress.ip_network("::ffff:0:0/96"),  # IPv4-mapped IPv6
]

# Specific cloud metadata IPs to block.
_BLOCKED_IPS = {
    ipaddress.ip_address("169.254.169.254"),
    ipaddress.ip_address("fd00::1"),
}

_ALLOWED_SCHEMES = {"http", "https"}


class SSRFError(ValueError):
    """Raised when a URL targets a private/internal network resource."""


def _is_ip_blocked(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Return True if the IP address falls within a blocked network or is a known metadata IP."""
    if addr in _BLOCKED_IPS:
        return True
    return any(addr in network for network in _BLOCKED_NETWORKS)


def validate_url(url: str) -> str:
    """Validate a URL is safe from SSRF attacks.

    Checks:
    1. Scheme is http or https only.
    2. Hostname resolves to a public (non-private, non-reserved) IP.
    3. Not a cloud metadata endpoint (169.254.169.254).

    Args:
        url: The URL to validate.

    Returns:
        The original URL if it passes validation.

    Raises:
        SSRFError: If the URL targets a private/internal resource.
    """
    parsed = urlparse(url)

    # 1. Validate scheme
    if parsed.scheme not in _ALLOWED_SCHEMES:
        msg = f"URL scheme '{parsed.scheme}' is not allowed; only http/https permitted"
        raise SSRFError(msg)

    hostname = parsed.hostname
    if not hostname:
        msg = "URL has no hostname"
        raise SSRFError(msg)

    # 2. Resolve DNS and check all resulting IPs
    try:
        addr_infos = socket.getaddrinfo(hostname, parsed.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        msg = f"DNS resolution failed for hostname '{hostname}'"
        raise SSRFError(msg) from exc

    if not addr_infos:
        msg = f"No addresses found for hostname '{hostname}'"
        raise SSRFError(msg)

    for _family, _type, _proto, _canonname, sockaddr in addr_infos:
        ip_str = sockaddr[0]
        try:
            ip_addr = ipaddress.ip_address(ip_str)
        except ValueError:
            continue

        if _is_ip_blocked(ip_addr):
            logger.warning(
                "ssrf_blocked",
                url=url,
                hostname=hostname,
                resolved_ip=ip_str,
            )
            msg = (
                f"URL resolves to blocked IP address {ip_str}; "
                "access to private/internal networks is not allowed"
            )
            raise SSRFError(msg)

    return url
