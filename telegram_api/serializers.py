from rest_framework import serializers
from .models import TelegramGroups

class TelegramGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = TelegramGroups
        fields = ['group_id', 'name', 'username', 'telegram_chat_id']


class UpdateAPICredentialsSerializer(serializers.Serializer):
    admin_id = serializers.IntegerField(required=True)


class InputCodeSerializer(serializers.Serializer):
    code = serializers.IntegerField(required=True)


class InviteUsersSerializer(serializers.Serializer):
    user_ids = serializers.ListField(child=serializers.IntegerField(), allow_null=False, required=True)
    group_ids = serializers.ListField(child=serializers.IntegerField(), allow_null=False, required=True)


class RemoveUsersSerializer(serializers.Serializer):
    user_ids = serializers.ListField(child=serializers.IntegerField(), allow_null=False, required=True)
    group_ids = serializers.ListField(child=serializers.IntegerField(), allow_null=False, required=True)


class PostMessagesSerializer(serializers.Serializer):
    message = serializers.CharField(required=True)
    group_ids = serializers.ListField(child=serializers.IntegerField(), allow_null=False, required=True)
