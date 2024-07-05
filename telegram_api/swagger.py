from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
   openapi.Info(
      title="Telegram API",
      default_version='v1',
      description="API documentation for the Telegram management API",
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)
