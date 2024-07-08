from django.db import models


# Create your models here.
class Admins(models.Model):
    admin_id = models.IntegerField(unique=True, primary_key=True)
    name = models.CharField(max_length=100)
    username = models.CharField(max_length=100)
    api_id = models.IntegerField(unique=True)
    api_hash = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=13)
    telegram_user_id = models.IntegerField()

    def __str__(self):
        return f"{self.admin_id}. {self.name}"

    class Meta:
        verbose_name_plural = "Admins"
        verbose_name = "Admin"
        db_table = 'admins'


class TelegramGroups(models.Model):
    name = models.CharField(max_length=100)
    username = models.CharField(max_length=100, null=True, blank=True)
    telegram_chat_id = models.IntegerField(unique=True)
    group_id = models.IntegerField(unique=True, primary_key=True)
    admin = models.ForeignKey(Admins, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.group_id}. {self.name}"

    class Meta:
        verbose_name_plural = "Telegram Groups"
        verbose_name = "Telegram Group"
        db_table = 'telegram_groups'


# class Post(models.Model):
#     user = models.ForeignKey(Users, on_delete=models.CASCADE)
#     groups = models.ForeignKey(TelegramGroups, on_delete=models.CASCADE)
#
#     def __str__(self):
#         return self.user.name
#
#     class Meta:
#         verbose_name_plural = "Posts"
#         verbose_name = "Post"
#         db_table = 'post'


class Users(models.Model):
    name = models.CharField(max_length=100)
    username = models.CharField(max_length=100, unique=True)
    user_id = models.IntegerField(unique=True, primary_key=True)

    def __str__(self):
        return f"{self.user_id}. {self.name}"

    class Meta:
        verbose_name_plural = "Users"
        verbose_name = "User"
        db_table = 'users'
