from django.contrib import admin
from django.urls import path, re_path
from telegram_api import views
from telegram_api.swagger import schema_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('update_api_credentials/', views.UpdateAPICredentialsView.as_view(), name='update_api_credentials'),
    path('input_code/', views.InputCodeView.as_view(), name='input_code'),
    path('get_groups/', views.GetGroupsView.as_view(), name='get_groups'),
    path('invite_user/', views.InviteUsersView.as_view(), name='invite_user'),
    path('remove_user/', views.RemoveUsersView.as_view(), name='remove_user'),
    path('post_message/', views.PostMessageToGroupsView.as_view(), name='post_message'),
    path('get_active_groups/', views.GetActiveGroupsView.as_view(), name='get_active_groups'),
    # path('list_groups/', views.ListGroupsView.as_view(), name='list_groups'),
    re_path(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]
