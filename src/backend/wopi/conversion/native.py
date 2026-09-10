"""Native conversion uses the existing converter and durable copy publication."""

import mimetypes
from contextlib import contextmanager
from pathlib import PurePosixPath
from types import SimpleNamespace

from django.conf import settings
from django.core.cache import cache

from core.services.storage_quota import StorageWriteConflict
from core.services.storage_spaces import authorize
from wopi.conversion.policy import is_forced_conversion, target_extension_for
from wopi.conversion.services import resolve_backend
from wopi.services.access import AccessUserMountEntryService


def native_conversion_target(filename):
    """Advertise only configured conversions, without constructing storage clients."""
    extension = PurePosixPath(filename).suffix.lstrip(".").lower()
    options = settings.WOPI_CLIENTS_CONFIGURATION.get("onlyoffice", {}).get("options", {})
    source = SimpleNamespace(extension=extension, mimetype=mimetypes.guess_type(filename)[0])
    if (
        not settings.STORAGE_UNIFIED_ENABLED
        or not settings.WOPI_SRC_BASE_URL
        or not settings.WOPI_ONLYOFFICE_CONVERT_JWT_SECRET
        or not options.get("ConvertServiceUrl")
        or not is_forced_conversion(source, options)
    ):
        return None
    return target_extension_for(extension)


@contextmanager
def converted_native_source(job, source):
    """Convert outside namespace locks so the converter can read its bounded WOPI source."""
    extension = native_conversion_target(source.name)
    if source.backend.family != "mount" or extension != job.payload["conversion"]:
        raise StorageWriteConflict("The requested conversion is no longer available.")
    authorize(source.space, job.actor, source.path, write=True)
    attempts = int(job.payload.get("conversion_attempts", 0))
    if attempts >= 3:
        raise StorageWriteConflict("Conversion failed repeatedly. Check the converter and retry.")
    job.payload = {**job.payload, "conversion_attempts": attempts + 1}
    job.save(update_fields=["payload", "updated_at"])
    observed = job.payload["observation"]
    token, _, file_id = AccessUserMountEntryService().insert_new_access(
        mount_id=str(source.space.pk),
        normalized_path=source.path,
        user=job.actor,
        observed_version=observed["version"],
        object_identity=observed["identity"],
    )
    cache.touch(token, timeout=settings.WOPI_CONVERSION_SOURCE_TOKEN_TIMEOUT)
    url = (
        f"{settings.WOPI_SRC_BASE_URL.rstrip('/')}/api/{settings.API_VERSION}"
        f"/wopi/mount-files/{file_id}/contents/?access_token={token}"
    )
    item = SimpleNamespace(
        id=source.reference.pk,
        filename=source.name,
        extension=PurePosixPath(source.name).suffix.lstrip("."),
    )
    try:
        options = settings.WOPI_CLIENTS_CONFIGURATION["onlyoffice"]["options"]
        with resolve_backend(options).convert(item, url, extension) as converted:
            yield converted
    finally:
        cache.delete(token)
