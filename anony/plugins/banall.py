# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic

from pyrogram import filters, types
from anony import app, lang


@app.on_message(filters.command(["banall"]) & filters.user(app.owner) & filters.group)
@lang.language()
async def _banall(_, m: types.Message):
    sent = await m.reply_text("🔄 Banning all members...")
    banned = 0
    failed = 0
    skipped = 0
    me = (await app.get_me()).id

    async for member in app.get_chat_members(m.chat.id):
        user = member.user
        if user.is_bot:
            skipped += 1
            continue
        if member.status in (
            types.ChatMemberStatus.ADMINISTRATOR,
            types.ChatMemberStatus.OWNER,
        ):
            skipped += 1
            continue
        if user.id == me or user.id == app.owner:
            skipped += 1
            continue
        try:
            await app.ban_chat_member(m.chat.id, user.id)
            banned += 1
        except Exception:
            failed += 1

    await sent.edit_text(
        f"✅ <b>Ban All Complete!</b>\n\n"
        f"├ <b>Banned:</b> {banned}\n"
        f"├ <b>Failed:</b> {failed}\n"
        f"└ <b>Skipped (admins/bots):</b> {skipped}"
    )
