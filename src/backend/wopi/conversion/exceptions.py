"""Exceptions raised by legacy WOPI conversion services."""


class ConversionError(Exception):
    """Base conversion exception."""


class ConversionRejected(ConversionError):
    """Raised when a conversion request is not eligible."""


class ConversionPermissionDenied(ConversionError):
    """Raised when the user cannot convert the item."""


class ConversionMisconfigured(ConversionError):
    """Raised when operator configuration is missing or invalid."""


class ConversionProviderError(ConversionError):
    """Raised when the conversion provider fails."""
