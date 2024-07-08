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
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

load_dotenv()

client = None
groups_file = 'groups.json'

async def initialize_telegram_client(api_id, api_hash, phone_number):
    global client
    if client:
        await client.disconnect()
    if os.path.exists(f'session_name.session'):
        os.remove(f'session_name.session')
    client = TelegramClient('session_name', api_id, api_hash)
    await client.connect()
    if not await client.is_user_authorized():
        await client.send_code_request(phone_number)
        return "Verification code sent"
    return client

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

        result = run_async(initialize_telegram_client(api_id, api_hash, phone_number))

        if isinstance(result, dict) and 'error' in result:
            return Response(result, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        request.session['admin_id'] = admin_id

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

async def get_group_usernames_by_ids(group_ids):
    return await sync_to_async(list)(
        TelegramGroups.objects.filter(group_id__in=group_ids).values_list('username', flat=True))

async def get_users_by_ids(user_ids):
    users = await sync_to_async(list)(
        Users.objects.filter(user_id__in=user_ids).values('user_id', 'username')
    )
    return users


async def invite_users_to_groups_inner(user_ids, group_ids):
    global client
    if not client or not client.is_connected():
        return [{"error": "Telegram client is not connected."}]

    group_usernames = await get_group_usernames_by_ids(group_ids)
    users = await get_users_by_ids(user_ids)

    results = []
    operation_count = 0

    for user in users:
        try:
            if user['username']:
                user_entity = await client.get_input_entity(user['username'])
            else:
                user_entity = InputPeerUser(user['user_id'], 0)
        except Exception as e:
            results.append({"error": f"Error fetching user entity for {user['user_id']}: {e}"})
            continue

        for group_username in group_usernames:
            try:
                group = await client.get_entity(f'@{group_username}')
                await client(InviteToChannelRequest(group, [user_entity]))
                results.append({"message": f"User {user['user_id']} invited to {group_username}"})
                operation_count += 1

                if operation_count % 50 == 0:
                    await asyncio.sleep(600)

            except UserPrivacyRestrictedError:
                results.append(
                    {"error": f"Cannot invite {user['user_id']} to {group_username} due to privacy settings."})
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds)
            except ChatAdminRequiredError:
                results.append(
                    {"error": f"Cannot invite {user['user_id']} to {group_username}. Account lacks admin privileges."})
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


async def remove_users_from_groups_inner(user_ids, group_ids):
    global client
    if not client or not client.is_connected():
        return [{"error": "Telegram client is not connected."}]

    group_usernames = await get_group_usernames_by_ids(group_ids)
    users = await get_users_by_ids(user_ids)

    results = []
    operation_count = 0

    for user in users:
        try:
            if user['username']:
                user_entity = await client.get_input_entity(user['username'])
            else:
                user_entity = InputPeerUser(user['user_id'], 0)
        except Exception as e:
            results.append({"error": f"Error fetching user entity for {user['user_id']}: {e}"})
            continue

        for group_username in group_usernames:
            try:
                group = await client.get_entity(f'@{group_username}')
                banned_rights = ChatBannedRights(until_date=None, view_messages=True)
                await client(EditBannedRequest(channel=group, participant=user_entity, banned_rights=banned_rights))
                results.append({"message": f"User {user['user_id']} removed from {group_username}"})
                operation_count += 1

                if operation_count % 50 == 0:
                    await asyncio.sleep(600)

            except UserPrivacyRestrictedError:
                results.append(
                    {"error": f"Cannot remove {user['user_id']} from {group_username} due to privacy settings."})
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds)
            except ChatAdminRequiredError:
                results.append({
                                   "error": f"Cannot remove {user['user_id']} from {group_username}. Account lacks admin privileges."})
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


async def post_message_to_groups_inner(message, group_ids):
    global client
    if not client or not client.is_connected():
        return [{"error": "Telegram client is not connected."}]

    group_usernames = await get_group_usernames_by_ids(group_ids)

    results = []
    operation_count = 0

    for group_username in group_usernames:
        try:
            group = await client.get_entity(f'@{group_username}')
            await client.send_message(group, message)
            results.append({"message": f"Message sent to {group_username}"})
            operation_count += 1

            if operation_count % 50 == 0:
                await asyncio.sleep(600)

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
    print(admin_group_usernames)
    return admin_group_usernames


async def get_dialogs():
    global client
    if client is None:
        raise Exception("Telegram client is not initialized")
    dialogs = await client(GetDialogsRequest(
        offset_date=None,
        offset_id=0,
        offset_peer=InputPeerEmpty(),
        limit=200,
        hash=0
    ))
    return dialogs

def fetch_groups_by_telegram_user_id(telegram_user_id):
    try:
        dialogs = run_async(get_dialogs())

        result = []
        for dialog in dialogs.chats:
            try:
                entity = dialog
                if isinstance(entity, Channel) and entity.username:
                    group = {
                        'name': entity.title,
                        'username': entity.username,
                        'group_id': entity.id,
                    }
                    result.append(group)
            except Exception as e:
                print(f"Error fetching group {entity.username if hasattr(entity, 'username') else 'unknown'}: {e}")
                continue

        return result

    except Exception as e:
        print(f"Error fetching groups: {str(e)}")
        return []

def save_groups_to_json(admin_id, groups):
    file_path = f'admin_{admin_id}_groups.json'
    with open(file_path, 'w') as f:
        json.dump(groups, f, indent=4)
    return file_path

class GetGroupsView(APIView):
    def get(self, request):
        admin_id = request.session.get('admin_id')

        if not admin_id:
            return Response({"error": "Admin ID is missing."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            admin = Admins.objects.get(admin_id=admin_id)

            run_async(initialize_telegram_client(admin.api_id, admin.api_hash, admin.phone_number))

            telegram_user_id = admin.telegram_user_id
            groups = fetch_groups_by_telegram_user_id(telegram_user_id)

            file_path = save_groups_to_json(admin_id, groups)
            print(f"Groups saved to {file_path}")
            return Response({"message": f"Groups saved to {file_path}"})

        except Admins.DoesNotExist:
            return Response({"error": "Admin not found."}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            print(f"Error in GetGroupsView: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

async def get_active_groups_inner():
    global client
    if client is None:
        raise Exception("Telegram client is not initialized")

    dialogs = await client(GetDialogsRequest(
        offset_date=None,
        offset_id=0,
        offset_peer=InputPeerEmpty(),
        limit=200,
        hash=0
    ))

    current_groups = {dialog.id: {
        'title': dialog.title,
        'username': dialog.username
    } for dialog in dialogs.chats if isinstance(dialog, Channel) and (dialog.megagroup or dialog.broadcast)}

    if not os.path.exists(groups_file):
        with open(groups_file, 'w') as f:
            json.dump(current_groups, f, indent=4)
        return {"message": "Initial group list saved."}

    with open(groups_file, 'r') as f:
        previous_groups = json.load(f)

    new_groups = {gid: details for gid, details in current_groups.items() if str(gid) not in previous_groups}

    response = {}
    if new_groups:
        response["new_groups_detected"] = len(new_groups)
        response["groups"] = new_groups
    else:
        response["message"] = "No new groups detected."

    with open(groups_file, 'w') as f:
        json.dump(current_groups, f, indent=4)

    return response

class GetActiveGroupsView(APIView):
    def get(self, request):
        admin_id = request.session.get('admin_id')

        if not admin_id:
            return Response({"error": "Admin ID is missing."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            admin = Admins.objects.get(admin_id=admin_id)
            api_id = admin.api_id
            api_hash = admin.api_hash
            phone_number = admin.phone_number

            # Initialize the Telegram client
            # result = run_async(initialize_telegram_client(api_id, api_hash, phone_number))

            # Fetch active groups
            response = run_async(get_active_groups_inner())
            return Response(response, status=status.HTTP_200_OK)

        except Admins.DoesNotExist:
            return Response({"error": "Admin not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(f"Error in GetActiveGroupsView: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)