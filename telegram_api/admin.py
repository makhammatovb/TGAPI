from django.contrib import admin
from .models import TelegramGroups, Admins, Users


# Register your models here.
admin.site.register(TelegramGroups)
admin.site.register(Admins)
admin.site.register(Users)