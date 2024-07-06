from django.urls import path
from . import views

urlpatterns = [
    path('update_api_credentials/', views.UpdateAPICredentialsView.as_view(), name='update_api_credentials'),
    path('input_code/', views.InputCodeView.as_view(), name='input_code'),
    path('get_groups/', views.GetGroupsView.as_view(), name='get_groups'),
    path('invite_user/', views.InviteUsersView.as_view(), name='invite_user'),
    path('remove_user/', views.RemoveUsersView.as_view(), name='remove_user'),
    path('post_message/', views.PostMessageToGroupsView.as_view(), name='post_message'),
]
