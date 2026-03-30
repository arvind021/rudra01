# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic
from pyrogram import filters, types
from anony import app, config

@app.on_message(filters.new_chat_members & filters.group)
async def welcome(_, m: types.Message):
    for member in m.new_chat_members:
        if member.is_bot:
            continue
        name = member.first_name or "User"
        username = f"@{member.username}" if member.username else "N/A"
        user_id = member.id
        text = (
            f"👋 <b>Welcome to {m.chat.title}!</b>\n\n"
            f"🙍 <b>Name:</b> {name}\n"
            f"👤 <b>Username:</b> {username}\n"
            f"🆔 <b>User ID:</b> <code>{user_id}</code>\n\n"
            f"🎵 Use /play to play songs."
        )
        keyboard = types.InlineKeyboardMarkup([
            [
                types.InlineKeyboardButton("🎵 Play Music", callback_data="help play"),
                types.InlineKeyboardButton("💫 Support", url=config.SUPPORT_CHAT),
            ]
        ])
        await m.reply_text(text, reply_markup=keyboard)
