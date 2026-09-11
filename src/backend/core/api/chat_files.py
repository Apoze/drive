"""Drive-authenticated browser copies, never authenticated by a Matrix token."""

from django.conf import settings

from rest_framework import exceptions, permissions, response
from rest_framework.settings import api_settings
from suite_identity.access import enabled, principal_id

from core.api.suite_file_chunks import SuiteFileChunksView
from core.api.suite_files import SuiteFileView


class ChatBrowserAccess:
    authentication_classes = api_settings.DEFAULT_AUTHENTICATION_CLASSES
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = api_settings.DEFAULT_PARSER_CLASSES

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not settings.CHAT_PUBLIC_URL or not enabled():
            raise exceptions.NotFound()
        if request.headers.get("X-Suite-Principal") != str(principal_id(request.user)):
            raise exceptions.PermissionDenied("Use the same suite account in Drive and Chat.")

    def input(self, request, purpose="read"):
        return request.data


class ChatFilesView(ChatBrowserAccess, SuiteFileView):
    http_method_names = ["get", "patch", "post", "options"]

    def get(self, request):
        result = response.Response({"principal": str(principal_id(request.user))})
        result["Cache-Control"] = "no-store"
        return result


class ChatFileChunksView(ChatBrowserAccess, SuiteFileChunksView):
    http_method_names = ["patch", "post", "options"]
