import os
import json
import asyncio
import threading
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from telethon import TelegramClient, errors
from telethon.errors import UserPrivacyRestrictedError, FloodWaitError, ChatAdminRequiredError
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty, Channel, ChatBannedRights, InputUser
from telethon.tl.functions.channels import InviteToChannelRequest, EditBannedRequest
from dotenv import load_dotenv
from .models import TelegramGroups, Admins, Users
from asgiref.sync import sync_to_async, async_to_sync
from telethon.tl.types import InputPeerUser

load_dotenv()

client = None

async def initialize_telegram_client(api_id, api_hash, phone_number):
    global client
    if client:
        await client.disconnect()
    if os.path.exists(f'session_name.session'):
        os.remove(f'session_name.session')
    client = TelegramClient('session_name', api_id, api_hash)
    await client.connect()
    await client.send_code_request(phone_number)

def run_async(coroutine):
    return asyncio.run_coroutine_threadsafe(coroutine, loop).result()

loop = asyncio.new_event_loop()
thread = threading.Thread(target=loop.run_forever)
thread.start()

class UpdateAPICredentialsView(APIView):
    def post(self, request):
        data = request.data
        admin_id = data.get('admin_id')

        if not admin_id:
            return Response({"error": "Admin ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            admin = Admins.objects.get(admin_id=admin_id)
        except Admins.DoesNotExist:
            return Response({"error": "Admin not found."}, status=status.HTTP_404_NOT_FOUND)

        api_id = admin.api_id
        api_hash = admin.api_hash
        phone_number = admin.phone_number

        os.environ['API_ID'] = str(api_id)
        os.environ['API_HASH'] = api_hash
        os.environ['PHONE_NUMBER'] = phone_number

        # Ensure client is reinitialized
        result = run_async(initialize_telegram_client(api_id, api_hash, phone_number))

        if isinstance(result, dict) and 'error' in result:
            return Response(result, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({"message": "API credentials updated and Telegram client reinitialized."})

class InputCodeView(APIView):
    def post(self, request):
        data = request.data
        code = data.get('code')

        if not code:
            return Response({"error": "Code is required."}, status=status.HTTP_400_BAD_REQUEST)

        async def complete_login():
            global client
            try:
                await client.sign_in(os.getenv('PHONE_NUMBER'), code)
                return {"message": "Login successful."}
            except errors.SessionPasswordNeededError:
                return {"error": "Two-step verification enabled. Password needed."}
            except Exception as e:
                return {"error": str(e)}

        result = run_async(complete_login())
        return Response(result)

# Fetch group usernames based on IDs
async def get_group_usernames_by_ids(group_ids):
    return await sync_to_async(list)(
        TelegramGroups.objects.filter(group_id__in=group_ids).values_list('username', flat=True))

# Fetch user details based on IDs
async def get_users_by_ids(user_ids):
    users = await sync_to_async(list)(
        Users.objects.filter(user_id__in=user_ids).values('user_id', 'username')
    )
    return users

# Invite users to groups
async def invite_users_to_groups_inner(user_ids, group_ids):
    global client
    if not client or not client.is_connected():
        return [{"error": "Telegram client is not connected."}]

    group_usernames = await get_group_usernames_by_ids(group_ids)
    users = await get_users_by_ids(user_ids)

    results = []
    for user in users:
        try:
            if user['username']:
                user_entity = await client.get_input_entity(user['username'])
            else:
                user_entity = InputPeerUser(user['user_id'], 0)  # Assuming 0 if access_hash is not needed or stored
        except Exception as e:
            results.append({"error": f"Error fetching user entity for {user['user_id']}: {e}"})
            continue

        for group_username in group_usernames:
            try:
                group = await client.get_entity(f'@{group_username}')
                await client(InviteToChannelRequest(group, [user_entity]))
                await asyncio.sleep(30)  # Adjust the sleep time as necessary
                results.append({"message": f"User {user['user_id']} invited to {group_username}"})
            except UserPrivacyRestrictedError:
                results.append({"error": f"Cannot invite {user['user_id']} to {group_username} due to privacy settings."})
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds)
            except ChatAdminRequiredError:
                results.append({"error": f"Cannot invite {user['user_id']} to {group_username}. Account lacks admin privileges."})
            except Exception as e:
                results.append({"error": f"An error occurred: {e}"})
    return results

class InviteUsersView(APIView):
    def post(self, request):
        data = request.data
        user_ids = data['user_ids']
        group_ids = data['group_ids']
        result = run_async(invite_users_to_groups_inner(user_ids, group_ids))
        return Response(result)

# Remove users from groups
async def remove_users_from_groups_inner(user_ids, group_ids):
    global client
    if not client or not client.is_connected():
        return [{"error": "Telegram client is not connected."}]

    group_usernames = await get_group_usernames_by_ids(group_ids)
    users = await get_users_by_ids(user_ids)

    results = []
    for user in users:
        try:
            if user['username']:
                user_entity = await client.get_input_entity(user['username'])
            else:
                user_entity = InputPeerUser(user['user_id'], 0)  # Assuming 0 if access_hash is not needed or stored
        except Exception as e:
            results.append({"error": f"Error fetching user entity for {user['user_id']}: {e}"})
            continue

        for group_username in group_usernames:
            try:
                group = await client.get_entity(f'@{group_username}')
                banned_rights = ChatBannedRights(until_date=None, view_messages=True)
                await client(EditBannedRequest(channel=group, participant=user_entity, banned_rights=banned_rights))
                await asyncio.sleep(30)  # Adjust the sleep time as necessary
                results.append({"message": f"User {user['user_id']} removed from {group_username}"})
            except UserPrivacyRestrictedError:
                results.append({"error": f"Cannot remove {user['user_id']} from {group_username} due to privacy settings."})
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds)
            except ChatAdminRequiredError:
                results.append({"error": f"Cannot remove {user['user_id']} from {group_username}. Account lacks admin privileges."})
            except Exception as e:
                results.append({"error": f"An error occurred: {e}"})
    return results

class RemoveUsersView(APIView):
    def post(self, request):
        data = request.data
        user_ids = data['user_ids']
        group_ids = data['group_ids']
        result = run_async(remove_users_from_groups_inner(user_ids, group_ids))
        return Response(result)

# Post a message to groups
async def post_message_to_groups_inner(message, group_ids):
    global client
    if not client or not client.is_connected():
        return [{"error": "Telegram client is not connected."}]

    group_usernames = await get_group_usernames_by_ids(group_ids)

    results = []
    for group_username in group_usernames:
        try:
            group = await client.get_entity(f'@{group_username}')
            await client.send_message(group, message)
            await asyncio.sleep(900)  # Adjust the sleep time as necessary
            results.append({"message": f"Message sent to {group_username}"})
        except errors.UserPrivacyRestrictedError:
            results.append({"error": f"Cannot post message to {group_username}. Privacy settings restricted."})
        except errors.FloodWaitError as e:
            await asyncio.sleep(e.seconds)
            results.append({"error": f"Flood wait error for {group_username}. Waiting {e.seconds} seconds."})
        except errors.ChatAdminRequiredError:
            results.append({"error": f"Cannot post message to {group_username}. Admin privileges required."})
        except Exception as e:
            results.append({"error": f"Error posting message to {group_username}: {str(e)}"})
    return results

class PostMessageToGroupsView(APIView):
    def post(self, request):
        message = request.data.get('message')
        group_ids = request.data.get('group_ids')

        if not message or not group_ids:
            return Response({"error": "Message and group_ids are required."}, status=status.HTTP_400_BAD_REQUEST)

        if "all" in group_ids:
            admin_group_usernames = run_async(get_admin_group_usernames())
            group_ids = [group_id for group_id, username in admin_group_usernames.items()]

        results = run_async(post_message_to_groups_inner(message, group_ids))
        return Response(results)

# Fetch group usernames where the admin has privileges
async def get_admin_group_usernames():
    dialogs = await client(GetDialogsRequest(
        offset_date=None,
        offset_id=0,
        offset_peer=InputPeerEmpty(),
        limit=200,
        hash=0
    ))

    admin_group_usernames = {}
    for dialog in dialogs.chats:
        if isinstance(dialog, Channel) and (dialog.megagroup or dialog.broadcast) and dialog.username:
            try:
                full_channel = await client.get_permissions(dialog, 'me')
                if full_channel.is_admin:
                    admin_group_usernames[dialog.id] = dialog.username
            except Exception as e:
                print(f"Error fetching admin status for {dialog.username}: {e}")

    return admin_group_usernames

class GetGroupsView(APIView):
    def get(self, request):
        admin_group_usernames = run_async(get_admin_group_usernames())
        return Response({"admin_group_usernames": admin_group_usernames})
