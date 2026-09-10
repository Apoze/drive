"""Route key-only integrations to regular Items without buffering their S3 reads."""

from django.core.exceptions import ValidationError
from django.core.files import File

from botocore.exceptions import ClientError
from storages.backends.s3 import S3Storage


# S3 intentionally does not implement local paths or filesystem access times.
# pylint: disable-next=abstract-method
class RoutedS3Storage(S3Storage):
    """Keep default-bucket behavior for non-Item assets and native write APIs."""

    def _destination(self, name):
        # Django constructs storage before app models are necessarily loaded.
        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.models import Item  # noqa: PLC0415

        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.services.storage_connections import (  # noqa: PLC0415
            item_for_key,
            storage_for_item,
        )

        if "/item/" not in "/" + name:
            return None
        try:
            item = item_for_key(name)
        except (ValidationError, Item.DoesNotExist):
            raise FileNotFoundError("This storage reference is no longer available.") from None
        return (
            storage_for_item(item)
            if item.storage_backend_id and not item.storage_backend.legacy_s3
            else self
        )

    def exists(self, name):
        """An analysis never checks a different bucket from the file it will read."""
        try:
            storage = self._destination(name)
        except FileNotFoundError:
            return False
        if storage is None or storage is self:
            return super().exists(name)
        return storage.exists(name)

    def _open(self, name, mode="rb"):
        if mode not in {"r", "rb"}:
            return super()._open(name, mode)
        storage = self._destination(name)
        if storage is None:
            return super()._open(name, mode)
        try:
            result = storage.connection.meta.client.get_object(Bucket=storage.bucket_name, Key=name)
        except ClientError as exc:
            if str(exc.response.get("Error", {}).get("Code")) in {"404", "NoSuchKey"}:
                raise FileNotFoundError("This storage reference is no longer available.") from None
            raise
        # Django File supplies length/tell to multipart encoders; StreamingBody
        # keeps GET consumption bounded and closes the native HTTP connection.
        file = File(result["Body"], name=name)
        file.size = int(result["ContentLength"])
        return file
