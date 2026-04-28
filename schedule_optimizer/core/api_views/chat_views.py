import json
import os

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from core.models import (
    ChatConversation,
    ChatConversationPin,
    ChatMessage,
    ChatMessageAttachment,
    ChatMessageRead,
)


MAX_MESSAGE_LENGTH = 4000
MAX_ATTACHMENTS_PER_MESSAGE = 8
MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024  # 20MB
SYSTEM_MESSAGE_PREFIX = "__system__:"


def _full_name(user: User) -> str:
    name = user.get_full_name().strip()
    return name or user.username


def _role_display(user: User) -> str:
    try:
        return user.profile.get_role_display()
    except Exception:
        return ""


def _avatar_url(request, user: User) -> str:
    try:
        if user.profile.avatar:
            return request.build_absolute_uri(user.profile.avatar.url)
    except Exception:
        return ""
    return ""


def _ordered_pair(user_a: User, user_b: User):
    return (user_a, user_b) if user_a.id < user_b.id else (user_b, user_a)


def _conversation_participant_ids(conversation: ChatConversation):
    participant_ids = list(conversation.participants.values_list("id", flat=True))
    if participant_ids:
        return participant_ids

    fallback_ids = []
    if conversation.participant_a_id:
        fallback_ids.append(conversation.participant_a_id)
    if conversation.participant_b_id and conversation.participant_b_id not in fallback_ids:
        fallback_ids.append(conversation.participant_b_id)
    return fallback_ids


def _ensure_participant(conversation: ChatConversation, user: User) -> bool:
    if conversation.participants.filter(id=user.id).exists():
        return True
    return conversation.participant_a_id == user.id or conversation.participant_b_id == user.id


def _conversation_other_user(conversation: ChatConversation, current_user: User):
    if conversation.is_group:
        return None
    if conversation.participant_a_id and conversation.participant_b_id:
        return conversation.get_other_user(current_user)
    return conversation.participants.exclude(id=current_user.id).order_by("id").first()


def _ensure_direct_conversation(current_user: User, target_user: User) -> ChatConversation:
    first, second = _ordered_pair(current_user, target_user)
    conversation, _ = ChatConversation.objects.get_or_create(
        participant_a=first,
        participant_b=second,
        defaults={"is_group": False, "title": ""},
    )
    conversation.participants.add(first, second)
    return conversation


def _serialize_attachment(request, attachment: ChatMessageAttachment):
    return {
        "id": attachment.id,
        "name": attachment.original_name,
        "size": attachment.size,
        "url": request.build_absolute_uri(attachment.file.url),
        "ext": os.path.splitext(attachment.original_name or "")[1].lower(),
    }


def _serialize_message(request, message: ChatMessage, current_user: User):
    attachments = [_serialize_attachment(request, att) for att in message.attachments.all()]
    raw_text = message.text or ""
    is_system = raw_text.startswith(SYSTEM_MESSAGE_PREFIX)
    text = raw_text[len(SYSTEM_MESSAGE_PREFIX):].strip() if is_system else raw_text
    return {
        "id": message.id,
        "text": text,
        "created_at": message.created_at.isoformat(),
        "is_read": message.is_read,
        "sender_id": message.sender_id,
        "sender_name": _full_name(message.sender),
        "sender_avatar_url": _avatar_url(request, message.sender),
        "is_mine": message.sender_id == current_user.id,
        "is_system": is_system,
        "attachments": attachments,
    }


def _create_group_event_message(conversation: ChatConversation, actor: User, text: str):
    text = (text or "").strip()
    if not text:
        return None
    participant_ids = _conversation_participant_ids(conversation)
    with transaction.atomic():
        message = ChatMessage.objects.create(
            conversation=conversation,
            sender=actor,
            text=f"{SYSTEM_MESSAGE_PREFIX}{text}",
            is_read=len(participant_ids) <= 1,
        )
        now = timezone.now()
        read_states = [
            ChatMessageRead(message_id=message.id, user_id=uid, read_at=now if uid == actor.id else None)
            for uid in participant_ids
        ]
        if read_states:
            ChatMessageRead.objects.bulk_create(read_states, ignore_conflicts=True)
        conversation.save(update_fields=["updated_at"])
    return message


def _normalize_participant_ids(raw_ids, current_user_id):
    normalized_ids = []
    for pid in raw_ids or []:
        try:
            value = int(pid)
        except (TypeError, ValueError):
            continue
        if value > 0 and value not in normalized_ids and value != current_user_id:
            normalized_ids.append(value)
    return normalized_ids


def _can_manage_group(conversation: ChatConversation, user: User) -> bool:
    if not conversation.is_group or not _ensure_participant(conversation, user):
        return False
    if user.is_superuser:
        return True
    if conversation.created_by_id and conversation.created_by_id == user.id:
        return True
    try:
        return user.profile.role == "manager"
    except Exception:
        return False


def _last_message_payload(message: ChatMessage):
    if not message:
        return None
    text = (message.text or "").strip()
    if text.startswith(SYSTEM_MESSAGE_PREFIX):
        text = text[len(SYSTEM_MESSAGE_PREFIX):].strip()
    if not text and message.attachments.exists():
        text = f"Вложений: {message.attachments.count()}"
    return {
        "text": text,
        "sender_name": _full_name(message.sender),
        "created_at": message.created_at.isoformat(),
    }


@login_required
@require_http_methods(["GET"])
def api_chat_users(request):
    query = request.GET.get("q", "").strip()

    users = (
        User.objects.select_related("profile")
        .filter(is_active=True)
        .exclude(id=request.user.id)
    )

    if query:
        users = users.filter(
            Q(username__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(profile__patronymic__icontains=query)
            | Q(email__icontains=query)
        )

    users = users.order_by("last_name", "first_name", "username")[:500]
    data = [
        {
            "id": u.id,
            "display_name": _full_name(u),
            "username": u.username,
            "role": _role_display(u),
            "email": u.email or "",
            "avatar_url": _avatar_url(request, u),
        }
        for u in users
    ]
    return JsonResponse({"success": True, "users": data})


@login_required
@require_http_methods(["POST"])
def api_chat_start_conversation(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        payload = {}

    target_user_id = payload.get("user_id")
    if not target_user_id:
        return JsonResponse({"success": False, "error": "Не выбран пользователь."}, status=400)

    target_user = get_object_or_404(User, id=target_user_id, is_active=True)
    if target_user.id == request.user.id:
        return JsonResponse({"success": False, "error": "Нельзя создать диалог с самим собой."}, status=400)

    conversation = _ensure_direct_conversation(request.user, target_user)
    return JsonResponse({"success": True, "conversation_id": conversation.id})


@login_required
@require_http_methods(["POST"])
def api_chat_create_group(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        payload = {}

    raw_title = (payload.get("title") or "").strip()
    normalized_ids = _normalize_participant_ids(payload.get("participant_ids"), request.user.id)

    selected_users = list(
        User.objects.filter(id__in=normalized_ids, is_active=True).order_by("last_name", "first_name", "username")
    )

    all_participant_ids = [request.user.id] + [u.id for u in selected_users]
    if len(all_participant_ids) < 2:
        return JsonResponse({"success": False, "error": "Для группы нужен минимум один дополнительный участник."}, status=400)

    title = raw_title[:200] if raw_title else f"Группа {request.user.username}"
    conversation = ChatConversation.objects.create(
        is_group=True,
        title=title,
        participant_a=None,
        participant_b=None,
        created_by=request.user,
    )
    conversation.participants.set(all_participant_ids)
    return JsonResponse({"success": True, "conversation_id": conversation.id})


@login_required
@require_http_methods(["POST"])
def api_chat_update_group(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        payload = {}

    conversation_id = payload.get("conversation_id")
    if not conversation_id:
        return JsonResponse({"success": False, "error": "Не выбрана группа."}, status=400)

    conversation = get_object_or_404(ChatConversation.objects.prefetch_related("participants"), id=conversation_id)
    if not _can_manage_group(conversation, request.user):
        return JsonResponse({"success": False, "error": "Нет прав на изменение группы."}, status=403)

    title = payload.get("title", None)
    add_ids = _normalize_participant_ids(payload.get("add_participant_ids"), request.user.id)
    remove_ids = _normalize_participant_ids(payload.get("remove_participant_ids"), request.user.id)

    current_ids = set(conversation.participants.values_list("id", flat=True))
    new_ids = set(current_ids)
    if add_ids:
        valid_add_ids = set(User.objects.filter(id__in=add_ids, is_active=True).values_list("id", flat=True))
        new_ids.update(valid_add_ids)
    if remove_ids:
        new_ids.difference_update(set(remove_ids))
    new_ids.add(request.user.id)

    if len(new_ids) < 2:
        return JsonResponse({"success": False, "error": "В группе должно остаться минимум два участника."}, status=400)

    old_title = (conversation.title or "").strip()
    with transaction.atomic():
        if isinstance(title, str):
            title = title.strip()[:200]
            if title:
                conversation.title = title
                conversation.save(update_fields=["title", "updated_at"])
        conversation.participants.set(sorted(new_ids))
        conversation.save(update_fields=["updated_at"])

        added_ids = sorted(list(new_ids - current_ids))
        removed_ids = sorted(list(current_ids - new_ids))
        title_changed = bool(isinstance(title, str) and title and title != old_title)

        if title_changed:
            _create_group_event_message(
                conversation=conversation,
                actor=request.user,
                text=f"{_full_name(request.user)} изменил(а) название группы на «{conversation.title}».",
            )

        if added_ids:
            added_users = list(User.objects.filter(id__in=added_ids).order_by("last_name", "first_name", "username"))
            added_names = ", ".join(_full_name(u) for u in added_users)
            _create_group_event_message(
                conversation=conversation,
                actor=request.user,
                text=f"{_full_name(request.user)} добавил(а) в группу: {added_names}.",
            )

        if removed_ids:
            removed_users = list(User.objects.filter(id__in=removed_ids).order_by("last_name", "first_name", "username"))
            removed_names = ", ".join(_full_name(u) for u in removed_users)
            _create_group_event_message(
                conversation=conversation,
                actor=request.user,
                text=f"{_full_name(request.user)} удалил(а) из группы: {removed_names}.",
            )

    return JsonResponse({"success": True, "conversation_id": conversation.id})


@login_required
@require_http_methods(["POST"])
def api_chat_delete_group(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        payload = {}

    conversation_id = payload.get("conversation_id")
    if not conversation_id:
        return JsonResponse({"success": False, "error": "Не выбрана группа."}, status=400)

    conversation = get_object_or_404(ChatConversation, id=conversation_id)
    if not _can_manage_group(conversation, request.user):
        return JsonResponse({"success": False, "error": "Нет прав на удаление группы."}, status=403)

    deleted_id = conversation.id
    conversation.delete()
    return JsonResponse({"success": True, "deleted_conversation_id": deleted_id})


@login_required
@require_http_methods(["POST"])
def api_chat_leave_group(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        payload = {}

    conversation_id = payload.get("conversation_id")
    if not conversation_id:
        return JsonResponse({"success": False, "error": "Не выбрана группа."}, status=400)

    conversation = get_object_or_404(ChatConversation.objects.prefetch_related("participants"), id=conversation_id)
    if not conversation.is_group:
        return JsonResponse({"success": False, "error": "Покинуть можно только групповую беседу."}, status=400)
    if not _ensure_participant(conversation, request.user):
        return JsonResponse({"success": False, "error": "Вы не состоите в этой группе."}, status=403)

    current_ids = set(conversation.participants.values_list("id", flat=True))
    remaining_ids = set(current_ids)
    remaining_ids.discard(request.user.id)

    with transaction.atomic():
        ChatConversationPin.objects.filter(user=request.user, conversation=conversation).delete()

        if len(remaining_ids) < 2:
            deleted_id = conversation.id
            conversation.delete()
            return JsonResponse({"success": True, "deleted_conversation_id": deleted_id, "left": True})

        conversation.participants.set(sorted(remaining_ids))
        conversation.save(update_fields=["updated_at"])
        _create_group_event_message(
            conversation=conversation,
            actor=request.user,
            text=f"{_full_name(request.user)} покинул(а) группу.",
        )

    return JsonResponse({"success": True, "conversation_id": conversation.id, "left": True})


@login_required
@require_http_methods(["GET"])
def api_chat_conversations(request):
    conversations = (
        ChatConversation.objects.filter(
            Q(participants=request.user) | Q(participant_a=request.user) | Q(participant_b=request.user)
        )
        .select_related("participant_a", "participant_b", "created_by")
        .prefetch_related("participants")
        .distinct()
        .order_by("-updated_at")
    )

    conv_ids = [c.id for c in conversations]
    unread_counts = {
        row["message__conversation_id"]: row["cnt"]
        for row in (
            ChatMessageRead.objects.filter(
                message__conversation_id__in=conv_ids,
                user=request.user,
                read_at__isnull=True,
            )
            .exclude(message__sender=request.user)
            .values("message__conversation_id")
            .annotate(cnt=Count("id"))
        )
    }

    last_messages_map = {}
    last_messages = (
        ChatMessage.objects.filter(conversation_id__in=conv_ids)
        .select_related("sender")
        .prefetch_related("attachments")
        .order_by("conversation_id", "-created_at")
    )
    for msg in last_messages:
        if msg.conversation_id not in last_messages_map:
            last_messages_map[msg.conversation_id] = msg

    pinned_ids = set(
        ChatConversationPin.objects.filter(user=request.user, conversation_id__in=conv_ids)
        .values_list("conversation_id", flat=True)
    )

    data = []
    for conv in conversations:
        other_user = _conversation_other_user(conv, request.user)
        participants = list(conv.participants.all())
        members_count = len(participants)
        group_title = (conv.title or "").strip() or f"Группа #{conv.id}"
        display_name = group_title if conv.is_group else (_full_name(other_user) if other_user else "Диалог")

        if conv.is_group:
            subtitle = f"Участников: {members_count}"
        elif other_user:
            subtitle = _role_display(other_user) or ""
        else:
            subtitle = ""

        last_msg = last_messages_map.get(conv.id)
        payload = {
            "id": conv.id,
            "is_pinned": conv.id in pinned_ids,
            "is_group": conv.is_group,
            "title": conv.title or "",
            "display_name": display_name,
            "subtitle": subtitle,
            "members_count": members_count,
            "updated_at": conv.updated_at.isoformat(),
            "_updated_at_unix": conv.updated_at.timestamp(),
            "last_message": _last_message_payload(last_msg),
            "unread_count": unread_counts.get(conv.id, 0),
            "can_manage_group": _can_manage_group(conv, request.user),
            "other_user": (
                {
                    "id": other_user.id,
                    "display_name": _full_name(other_user),
                    "username": other_user.username,
                    "role": _role_display(other_user),
                    "avatar_url": _avatar_url(request, other_user),
                }
                if other_user
                else None
            ),
            "avatar_url": _avatar_url(request, other_user) if other_user else "",
        }
        data.append(payload)

    data.sort(key=lambda item: (0 if item["is_pinned"] else 1, -item["_updated_at_unix"]))
    for item in data:
        item.pop("_updated_at_unix", None)

    return JsonResponse({"success": True, "conversations": data})


@login_required
@require_http_methods(["POST"])
def api_chat_toggle_pin(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        payload = {}

    conversation_id = payload.get("conversation_id")
    if not conversation_id:
        return JsonResponse({"success": False, "error": "Не выбран диалог."}, status=400)

    conversation = get_object_or_404(ChatConversation, id=conversation_id)
    if not _ensure_participant(conversation, request.user):
        return JsonResponse({"success": False, "error": "Нет доступа к диалогу."}, status=403)

    pin = ChatConversationPin.objects.filter(user=request.user, conversation=conversation).first()
    pinned_payload = payload.get("pinned", None)
    desired_pinned = pinned_payload if isinstance(pinned_payload, bool) else (pin is None)

    if desired_pinned and pin is None:
        ChatConversationPin.objects.create(user=request.user, conversation=conversation)
        is_pinned = True
    elif not desired_pinned and pin is not None:
        pin.delete()
        is_pinned = False
    else:
        is_pinned = pin is not None

    return JsonResponse({"success": True, "is_pinned": is_pinned, "conversation_id": conversation.id})


@login_required
@require_http_methods(["GET"])
def api_chat_messages(request, conversation_id):
    conversation = get_object_or_404(ChatConversation.objects.prefetch_related("participants"), id=conversation_id)
    if not _ensure_participant(conversation, request.user):
        return JsonResponse({"success": False, "error": "Нет доступа к диалогу."}, status=403)

    after_id = request.GET.get("after_id")
    try:
        after_id_int = int(after_id) if after_id else None
    except (TypeError, ValueError):
        after_id_int = None

    ChatMessageRead.objects.filter(
        user=request.user,
        message__conversation=conversation,
        read_at__isnull=True,
    ).exclude(message__sender=request.user).update(read_at=timezone.now())

    conversation.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)

    messages_qs = conversation.messages.select_related("sender").prefetch_related("attachments").order_by("created_at")
    if after_id_int:
        messages_qs = messages_qs.filter(id__gt=after_id_int)

    messages_data = [_serialize_message(request, m, request.user) for m in messages_qs]

    other_user = _conversation_other_user(conversation, request.user)
    participants_data = [
        {
            "id": u.id,
            "display_name": _full_name(u),
            "username": u.username,
            "role": _role_display(u),
            "avatar_url": _avatar_url(request, u),
        }
        for u in conversation.participants.all().order_by("last_name", "first_name", "username")
    ]

    return JsonResponse(
        {
            "success": True,
            "conversation": {
                "id": conversation.id,
                "is_group": conversation.is_group,
                "title": conversation.title or "",
                "display_name": (conversation.title or f"Группа #{conversation.id}")
                if conversation.is_group
                else (_full_name(other_user) if other_user else "Диалог"),
                "subtitle": f"Участников: {len(participants_data)}"
                if conversation.is_group
                else (_role_display(other_user) if other_user else ""),
                "can_manage_group": _can_manage_group(conversation, request.user),
                "other_user": (
                    {
                        "id": other_user.id,
                        "display_name": _full_name(other_user),
                        "username": other_user.username,
                        "role": _role_display(other_user),
                        "avatar_url": _avatar_url(request, other_user),
                    }
                    if other_user
                    else None
                ),
                "avatar_url": _avatar_url(request, other_user) if other_user else "",
                "participants": participants_data,
            },
            "messages": messages_data,
        }
    )


@login_required
@require_http_methods(["POST"])
def api_chat_send_message(request):
    is_multipart = request.content_type and request.content_type.startswith("multipart/form-data")
    if is_multipart:
        conversation_id = request.POST.get("conversation_id")
        text = (request.POST.get("text") or "").strip()
        files = request.FILES.getlist("files")
    else:
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            payload = {}
        conversation_id = payload.get("conversation_id")
        text = (payload.get("text") or "").strip()
        files = []

    if not conversation_id:
        return JsonResponse({"success": False, "error": "Не выбран диалог."}, status=400)

    try:
        conversation_id = int(conversation_id)
    except (TypeError, ValueError):
        return JsonResponse({"success": False, "error": "Некорректный диалог."}, status=400)

    if len(text) > MAX_MESSAGE_LENGTH:
        return JsonResponse(
            {"success": False, "error": f"Сообщение слишком длинное (максимум {MAX_MESSAGE_LENGTH} символов)."},
            status=400,
        )
    if not text and not files:
        return JsonResponse({"success": False, "error": "Добавьте текст или вложение."}, status=400)
    if len(files) > MAX_ATTACHMENTS_PER_MESSAGE:
        return JsonResponse(
            {"success": False, "error": f"Можно прикрепить не более {MAX_ATTACHMENTS_PER_MESSAGE} файлов за раз."},
            status=400,
        )

    for f in files:
        if f.size > MAX_ATTACHMENT_BYTES:
            return JsonResponse(
                {"success": False, "error": f"Файл «{f.name}» превышает лимит 20 МБ."},
                status=400,
            )

    conversation = get_object_or_404(ChatConversation, id=conversation_id)
    if not _ensure_participant(conversation, request.user):
        return JsonResponse({"success": False, "error": "Нет доступа к диалогу."}, status=403)

    participant_ids = _conversation_participant_ids(conversation)
    with transaction.atomic():
        message = ChatMessage.objects.create(
            conversation=conversation,
            sender=request.user,
            text=text,
            is_read=len(participant_ids) <= 1,
        )

        attachments = []
        for f in files:
            attachments.append(
                ChatMessageAttachment(
                    message=message,
                    file=f,
                    original_name=f.name[:255],
                    size=int(f.size or 0),
                )
            )
        if attachments:
            ChatMessageAttachment.objects.bulk_create(attachments)

        now = timezone.now()
        read_states = [
            ChatMessageRead(message_id=message.id, user_id=uid, read_at=now if uid == request.user.id else None)
            for uid in participant_ids
        ]
        if read_states:
            ChatMessageRead.objects.bulk_create(read_states, ignore_conflicts=True)

        conversation.save(update_fields=["updated_at"])

    message = ChatMessage.objects.select_related("sender").prefetch_related("attachments").get(id=message.id)
    return JsonResponse({"success": True, "message": _serialize_message(request, message, request.user)})


@login_required
@require_http_methods(["GET"])
def api_chat_unread_count(request):
    unread_count = (
        ChatMessageRead.objects.filter(user=request.user, read_at__isnull=True)
        .exclude(message__sender=request.user)
        .count()
    )
    return JsonResponse({"success": True, "unread_count": unread_count, "has_unread": unread_count > 0})
