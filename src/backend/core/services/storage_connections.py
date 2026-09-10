"""Resolve explicit storage destinations and protected, versioned credentials."""

import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage, storages

from botocore.config import Config
from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from core.models import Item
from core.services.storage_network import confine_s3_client, validate_destination

_ITEM_KEY = re.compile(r"(?:^|/)item/([0-9a-fA-F-]{36})/")
_S3_FIELDS = {
    "endpoint_url",
    "bucket_name",
    "region_name",
    "addressing_style",
    "prefix",
    "tls_ca",
}
_CREDENTIAL_FIELDS = {"access_key", "secret_key", "security_token", "password"}


def _vault():
    """Only the deployment can supply encryption keys, never an API request."""
    try:
        path = settings.STORAGE_SECRET_KEY_FILE
        with Path(path).open("rb") as source:
            content = source.read(4097)
        if not content or len(content) > 4096:
            raise ValueError
        return MultiFernet([Fernet(line.strip()) for line in content.splitlines() if line.strip()])
    except (OSError, ValueError, AttributeError, TypeError):
        raise ValidationError("The storage credential vault is unavailable.") from None


def encrypt_credentials(backend, credentials):
    """Bind ciphertext to its connection so swapping database rows is rejected."""
    if not isinstance(credentials, dict) or set(credentials) - _CREDENTIAL_FIELDS:
        raise ValidationError("Unsupported storage credential fields.")
    if not credentials or any(
        not isinstance(value, str) or not value or len(value) > 4096
        for value in credentials.values()
    ):
        raise ValidationError("Storage credentials must be nonempty bounded strings.")
    payload = json.dumps({"connection": str(backend.pk), "credentials": credentials})
    return _vault().encrypt(payload.encode()).decode()


def decrypt_credentials(backend):
    """Keep plaintext confined to native connection construction."""
    if not backend.secret_ciphertext:
        return {}
    try:
        payload = json.loads(_vault().decrypt(backend.secret_ciphertext.encode()))
        if payload["connection"] != str(backend.pk):
            raise ValueError
        credentials = payload["credentials"]
        if not isinstance(credentials, dict) or set(credentials) - _CREDENTIAL_FIELDS:
            raise ValueError
        return credentials
    except (InvalidToken, ValueError, KeyError, TypeError):
        raise ValidationError("Storage credentials cannot be resolved.") from None


def validate_configuration(backend, *, check_network=False):
    """Validate administrator input without performing storage IO or echoing secrets."""
    config = backend.configuration
    if not isinstance(config, dict):
        raise ValidationError("Storage configuration must be an object.")
    if not backend.managed:
        return
    if backend.family == "s3":
        _validate_s3_configuration(config, check_network=check_network)
        return
    if backend.family != "mount":
        raise ValidationError("Unsupported storage family.")
    if (
        set(config) - {"provider", "params"}
        or not isinstance(config.get("params"), dict)
        or not isinstance(config.get("provider"), str)
    ):
        raise ValidationError("Invalid provider configuration.")
    # Provider configuration already has a validated, capability-based contract.
    # pylint: disable-next=import-outside-toplevel,cyclic-import
    from core.services.mounts_registry import (  # noqa: PLC0415
        MountRegistryValidationError,
        validate_mounts_registry,
    )

    params = config["params"]
    if any("secret" in key or "password" in key for key in params):
        raise ValidationError("Set credentials through the protected credential field.")
    try:
        validate_mounts_registry(
            [
                {
                    "mount_id": backend.registry_id,
                    "display_name": backend.name,
                    "provider": config["provider"],
                    "params": params,
                }
            ]
        )
    except MountRegistryValidationError:
        raise ValidationError("Invalid filesystem connection configuration.") from None
    if "server" in params and check_network:
        validate_destination(params["server"], params.get("port", 445))
    elif "root_dir" in params:
        root = Path(params["root_dir"]).resolve()
        if not any(
            root.is_relative_to(Path(value).resolve())
            for value in settings.STORAGE_ALLOWED_LOCAL_ROOTS
        ):
            raise ValidationError("This local storage root is not allowed.")
    elif "server" not in params:
        raise ValidationError("This provider cannot be configured through the web interface.")


def _validate_s3_configuration(config, *, check_network):
    """Validate S3 endpoint and object namespace options at the trust boundary."""
    if set(config) - _S3_FIELDS:
        raise ValidationError("Unsupported S3 configuration fields.")
    if "tls_ca" in config and (
        not isinstance(config["tls_ca"], str)
        or (config["tls_ca"] and config["tls_ca"] not in settings.STORAGE_CA_BUNDLES)
    ):
        raise ValidationError("Choose a deployment-managed certificate authority.")
    try:
        endpoint = urlsplit(config["endpoint_url"])
        if (
            endpoint.scheme not in {"https", "http"}
            or not endpoint.hostname
            or any((endpoint.username, endpoint.password, endpoint.query, endpoint.fragment))
            or endpoint.path not in {"", "/"}
        ):
            raise ValueError
        if endpoint.scheme == "http" and not settings.STORAGE_ALLOW_INSECURE_ENDPOINTS:
            raise ValueError
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{1,254}", config["bucket_name"]):
            raise ValueError
        prefix = config.get("prefix", "")
        if (
            not isinstance(prefix, str)
            or len(prefix) > 512
            or any(part in {".", ".."} for part in prefix.split("/"))
            or "\\" in prefix
            or "\x00" in prefix
        ):
            raise ValueError
        if config.get("addressing_style", "path") not in {"path", "virtual", "auto"}:
            raise ValueError
        if "region_name" in config and not re.fullmatch(
            r"[a-zA-Z0-9-]{1,64}", config["region_name"]
        ):
            raise ValueError
        if check_network:
            validate_destination(
                endpoint.hostname, endpoint.port or (443 if endpoint.scheme == "https" else 80)
            )
    except (KeyError, ValueError, TypeError):
        raise ValidationError("Invalid S3 connection configuration.") from None


def storage_for_backend(backend):
    """Construct a connection explicitly; never mutate global Django storage settings."""
    if backend.family != "s3":
        raise ValidationError("This resource is not on S3 storage.")
    if backend.legacy_s3:
        return default_storage
    validate_configuration(backend, check_network=True)
    credentials = decrypt_credentials(backend)
    if not credentials.get("access_key") or not credentials.get("secret_key"):
        raise ValidationError("S3 credentials are not configured.")
    options = {
        key: value
        for key, value in backend.configuration.items()
        if key not in {"prefix", "tls_ca"}
    }
    if ca := backend.configuration.get("tls_ca"):
        options["verify"] = settings.STORAGE_CA_BUNDLES[ca]
    options.update({key: value for key, value in credentials.items() if key != "password"})
    options["client_config"] = Config(
        connect_timeout=5,
        read_timeout=30,
        retries={"max_attempts": 2},
        proxies={},
        s3={"addressing_style": options.pop("addressing_style", "path")},
    )
    storage = storages.create_storage(
        {"BACKEND": "storages.backends.s3.S3Storage", "OPTIONS": options}
    )
    confine_s3_client(storage.connection.meta.client)
    return storage


def storage_for_item(item):
    """Legacy Items remain readable before the explicit-location migration."""
    if not item.storage_backend_id:
        return default_storage
    backend = item.storage_backend
    identity = (backend.pk, backend.configuration_generation)
    cached = item.__dict__.get("_native_storage")
    if cached and cached[0] == identity:
        return cached[1]
    storage = storage_for_backend(backend)
    item.__dict__["_native_storage"] = (identity, storage)
    return storage


def item_for_key(key):
    """Resolve only a complete, canonical Drive object key."""
    match = _ITEM_KEY.search(key)
    if not match:
        raise ValidationError("This key is not a registered Drive object.")
    item = Item.objects.select_related("storage_backend", "storage_space").get(pk=match[1])
    if not key.startswith(item.key_base + "/"):
        raise ValidationError("This key does not belong to the registered connection.")
    return item


def storage_for_key(key):
    """Key-only producers resolve their native destination through the Item identity."""
    if not _ITEM_KEY.search(key):
        return default_storage
    return storage_for_item(item_for_key(key))
