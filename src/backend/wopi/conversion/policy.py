"""Forced-conversion policy for WOPI legacy formats."""

from django.conf import settings


def _normalize(value):
    return value.lower() if isinstance(value, str) else value


def target_extension_for(source_extension):
    """Return the converted extension for a legacy source extension."""
    if not source_extension:
        return None

    return settings.WOPI_LEGACY_CONVERSION_TARGETS.get(source_extension.lower())


def is_forced_conversion(item, client_options):
    """Return true when active WOPI client options explicitly require conversion."""
    if not client_options:
        return False

    extension = _normalize(item.extension)
    forced_extensions = {
        _normalize(extension) for extension in client_options.get("ForceConvertExtensions") or []
    }
    if extension and extension in forced_extensions:
        return True

    mimetype = _normalize(item.mimetype)
    forced_mimetypes = {
        _normalize(mimetype) for mimetype in client_options.get("ForceConvertMimetypes") or []
    }
    if mimetype and mimetype in forced_mimetypes:
        return True

    return False
