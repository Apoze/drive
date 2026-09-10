"""Confine managed storage connections at socket creation, including DNS changes."""

import ipaddress
import socket
import sys

from django.conf import settings
from django.core.exceptions import ValidationError

from botocore.awsrequest import (
    AWSHTTPConnection,
    AWSHTTPConnectionPool,
    AWSHTTPSConnection,
    AWSHTTPSConnectionPool,
)
from urllib3.exceptions import NewConnectionError
from urllib3.util.connection import create_connection


def validate_destination(host, port):
    """Return vetted numeric addresses; metadata addresses are forbidden even on a LAN."""
    try:
        networks = [ipaddress.ip_network(value) for value in settings.STORAGE_ALLOWED_NETWORKS]
        addresses = {
            ipaddress.ip_address(result[4][0])
            for result in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        }
    except (ValueError, OSError, TypeError):
        raise ValidationError("The storage destination cannot be resolved.") from None
    if not addresses or len(addresses) > 16:
        raise ValidationError("The storage destination cannot be resolved.")
    for original in addresses:
        address = getattr(original, "ipv4_mapped", None) or original
        if address.is_link_local or address.is_unspecified or address.is_multicast:
            raise ValidationError("This storage destination is not allowed.")
        if not (
            any(address in network for network in networks)
            or (settings.STORAGE_ALLOW_PUBLIC_ENDPOINTS and address.is_global)
        ):
            raise ValidationError("This storage destination is outside the allowed networks.")
    return sorted(str(address) for address in addresses)


class _VettedSocket:
    """Keep the original hostname for TLS/signatures and connect to its vetted IP only."""

    # These attributes are supplied by the native HTTP(S) connection base.
    host: str
    port: int
    timeout: float
    source_address: tuple | None
    socket_options: list | None

    def _new_conn(self):
        for address in validate_destination(self.host, self.port):
            try:
                connected = create_connection(
                    (address, self.port),
                    self.timeout,
                    source_address=self.source_address,
                    socket_options=self.socket_options,
                )
                sys.audit("http.client.connect", self, self.host, self.port)
                return connected
            except OSError:
                continue
        raise NewConnectionError(self, "The storage destination is unavailable.")


class _StorageHTTPConnection(_VettedSocket, AWSHTTPConnection):
    """Preserve botocore's Expect/Continue behavior on approved HTTP endpoints."""


class _StorageHTTPSConnection(_VettedSocket, AWSHTTPSConnection):
    """Preserve botocore TLS validation and SNI on approved HTTPS endpoints."""


class _StorageHTTPPool(AWSHTTPConnectionPool):
    ConnectionCls = _StorageHTTPConnection


class _StorageHTTPSPool(AWSHTTPSConnectionPool):
    ConnectionCls = _StorageHTTPSConnection


def confine_s3_client(client):
    """Replace this client's pool classes only; never patch global SDK behavior.

    The private botocore session seam is qualified by the real two-bucket test.
    Recheck it when updating botocore/urllib3. TLS remains in their native classes.
    """
    # pylint: disable-next=protected-access
    client._endpoint.http_session._manager.pool_classes_by_scheme = {  # noqa: SLF001
        "http": _StorageHTTPPool,
        "https": _StorageHTTPSPool,
    }
