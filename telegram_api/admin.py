from django.contrib import admin
from .models import TelegramGroups, Admins, Users


# Register your models here.
@admin.register(TelegramGroups)
class TelegramGroupsAdmin(admin.ModelAdmin):
    list_display = ('name', 'username', 'group_id', 'admin')
    search_fields = ('name', 'username', 'admin__username')

admin.site.register(Admins)
admin.site.register(Users)