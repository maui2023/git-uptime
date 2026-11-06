"""Utility functions for Sabily Uptime Monitor.

Handles URL validation, SSRF protection, IP address checks, and date/time formatting.
"""

from __future__ import annotations

import datetime
import ipaddress
import socket
import urllib.parse
from typing import Optional, Tuple


# Private and reserved IPv4 and IPv6 networks for SSRF protection
PRIVATE_NETWORKS = [
    # IPv4 loopback, private, link-local, carrier-grade NAT, multicast, reserved
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    # IPv6 loopback, private, link-local, unique-local, documentation, multicast
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("2001:db8::/32"),
    ipaddress.ip_network("ff00::/8"),
    ipaddress.ip_network("::/128"),
]


def is_ip_private_or_reserved(ip_str: str) -> bool:
    """Check if an IP string belongs to a private, loopback, link-local, or reserved network."""
    try:
        ip = ipaddress.ip_address(ip_str)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return True
        for net in PRIVATE_NETWORKS:
            if ip in net:
                return True
        return False
    except ValueError:
        return True


def resolve_and_validate_hostname(hostname: str, port: int = 80) -> Tuple[bool, Optional[str], Optional[str]]:
    """Resolve a hostname to IP addresses and ensure none point to private/reserved ranges.

    Returns:
        (is_valid, resolved_ip, error_message)
    """
    if not hostname:
        return False, None, "Hostname is empty"

    # Check if hostname is already an IP address
    try:
        ip = ipaddress.ip_address(hostname)
        if is_ip_private_or_reserved(str(ip)):
            return False, str(ip), f"Destination IP {ip} is private/reserved (SSRF protection)"
        return True, str(ip), None
    except ValueError:
        pass  # It is a domain name, proceed to DNS resolution

    try:
        addrinfo = socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
        if not addrinfo:
            return False, None, f"DNS resolution failed for {hostname}"

        resolved_ips = []
        for item in addrinfo:
            sockaddr = item[4]
            ip_str = sockaddr[0]
            resolved_ips.append(ip_str)
            if is_ip_private_or_reserved(ip_str):
                return False, ip_str, f"Host {hostname} resolved to private/reserved IP {ip_str} (SSRF protection)"

        primary_ip = resolved_ips[0] if resolved_ips else None
        return True, primary_ip, None
    except socket.gaierror as e:
        return False, None, f"DNS resolution error: {e}"
    except Exception as e:
        return False, None, f"Socket error during resolution: {e}"


def validate_url(url: str) -> Tuple[bool, Optional[str]]:
    """Validate URL scheme, host, and prevent SSRF to internal networks.

    Returns:
        (is_valid, error_message)
    """
    if not url or not isinstance(url, str):
        return False, "URL must be a non-empty string"

    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False, f"Unsupported URL scheme '{parsed.scheme}'. Only http and https are allowed."

    if not parsed.hostname:
        return False, "URL does not contain a valid hostname"

    # Block local loopback aliases
    lower_host = parsed.hostname.lower()
    if lower_host in ("localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback"):
        return False, "Access to localhost is prohibited"

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    is_valid, _, error = resolve_and_validate_hostname(parsed.hostname, port)
    if not is_valid:
        return False, error

    return True, None


def get_iso_now() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def get_date_str_now() -> str:
    """Return current UTC date in YYYY-MM-DD format."""
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def parse_iso_datetime(iso_str: str) -> Optional[datetime.datetime]:
    """Parse an ISO 8601 string into a timezone-aware datetime."""
    if not iso_str:
        return None
    try:
        # Handle 'Z' suffix
        cleaned = iso_str.replace("Z", "+00:00")
        dt = datetime.datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt
    except Exception:
        return None
