#!/usr/bin/env python
# pylint: disable=unused-argument
# This program is dedicated to the public domain under the CC0 license.

import logging
import json
import random
from datetime import datetime, timedelta

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

TOKEN = '8634054649:AAHvbJ6VvKtSrNwNSuJcYTjRSdywGTwP4AU' # Replace with your telegram bot token
CHANNEL_ID = '-1003729366902'  # Replace with your channel ID
ADMIN_IDS = [8551549206]  # Replace with the Telegram user IDs of the admins

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# User data file
users_file = 'users.txt'

# States
START, CAPTCHA, MOVE_RED_SQUARE = range(3)

# List of emojis to use in captcha
emojis = [
    '🔴 Red', '🟢 Green', '🔵 Blue', '🟡 Yellow', '🟠 Orange', '🟣 Purple',
    '⚪ White', '⚫ Black', '🟤 Brown', '⛷️ Skis', '🏃‍♂️ Man Running',
    '🚴‍♂️ Man Biking', '🤸‍♂️ Man Cartwheeling', '🏊‍♂️ Man Swimming',
    '🚵‍♂️ Man Mountain Biking', '🤾‍♂️ Man Playing Handball'
]

def load_users():
    try:
        with open(users_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_users(users):
    with open(users_file, 'w') as f:
        json.dump(users, f, indent=4)

users = load_users()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = str(update.effective_user.id)
    if user_id not in users:
        users[user_id] = {
            'joined': False,
            'last_invite': None,
            'invites_left': 3,
            'admin': user_id in ADMIN_IDS
        }
        save_users(users)

    if users[user_id]['joined']:
        await update.message.reply_text("You are already verified! 🎉")
    else:
        if random.choice([True, False]):
            await send_captcha(update, context)
            return CAPTCHA
        else:
            await send_move_red_square_captcha(update, context)
            return MOVE_RED_SQUARE

async def send_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    correct_emoji = random.choice(emojis)
    correct_text = correct_emoji.split()[1]
    choices = random.sample(emojis, 7)  # Pick 7 random emojis
    if correct_emoji not in choices:
        choices.append(correct_emoji)
    random.shuffle(choices)  # Shuffle to ensure random order

    buttons = [
        [InlineKeyboardButton(emoji, callback_data=emoji.split()[1]) for emoji in choices[:4]],
        [InlineKeyboardButton(emoji, callback_data=emoji.split()[1]) for emoji in choices[4:]]
    ]

    keyboard = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(f"🛑 Which emoji is {correct_emoji}? Select the correct one below:", reply_markup=keyboard)

    context.user_data['captcha_correct'] = correct_text
    return CAPTCHA

async def send_move_red_square_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    correct_position = random.randint(0, 7)
    initial_position = 0
    context.user_data['correct_position'] = correct_position
    context.user_data['current_position'] = initial_position

    await update.message.reply_text(
        f"🛑 Align the red squares by moving the bottom red square left or right and pressing Accept.\n"
        f"{''.join(['🟩' if i != correct_position else '🟥' for i in range(8)])}\n"
        f"{''.join(['🟩' if i != initial_position else '🟥' for i in range(8)])}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️", callback_data='left'), InlineKeyboardButton("➡️", callback_data='right')],
            [InlineKeyboardButton("✅ Accept", callback_data='accept')]
        ])
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)

    if query.data == context.user_data.get('captcha_correct'):
        users[user_id]['joined'] = True
        users[user_id]['last_invite'] = str(datetime.now())
        users[user_id]['invites_left'] -= 1
        save_users(users)
        await query.edit_message_text(text="✅ Captcha completed! Here is your invite link: 🎉")
        expire_date = datetime.now() + timedelta(seconds=10)
        invite_link = await context.bot.create_chat_invite_link(CHANNEL_ID, expire_date=expire_date)
        await query.message.reply_text("👉 Join Channel", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Join", url=invite_link.invite_link)]]))
    else:
        await query.edit_message_text(text="❌ Incorrect. Please try again by sending /start.")

async def move_red_square_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    action = query.data

    current_position = context.user_data['current_position']
    correct_position = context.user_data['correct_position']

    if action == 'left' and current_position > 0:
        current_position -= 1
    elif action == 'right' and current_position < 7:
        current_position += 1
    elif action == 'accept':
        if current_position == correct_position:
            users[user_id]['joined'] = True
            users[user_id]['last_invite'] = str(datetime.now())
            users[user_id]['invites_left'] -= 1
            save_users(users)
            await query.edit_message_text(text="✅ Captcha completed! Here is your invite link: 🎉")
            invite_link = await context.bot.create_chat_invite_link(CHANNEL_ID, member_limit=1)
            await query.message.reply_text("👉 Join Channel", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Join", url=invite_link.invite_link)]]))
            return

    context.user_data['current_position'] = current_position

    await query.edit_message_text(
        f"🛑 Align the red squares by moving the bottom red square left or right and pressing Accept.\n"
        f"{''.join(['🟩' if i != correct_position else '🟥' for i in range(8)])}\n"
        f"{''.join(['🟩' if i != current_position else '🟥' for i in range(8)])}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️", callback_data='left'), InlineKeyboardButton("➡️", callback_data='right')],
            [InlineKeyboardButton("✅ Accept", callback_data='accept')]
        ])
    )

async def create_invite(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.effective_user.id)
    if users[user_id]['joined']:
        last_invite = datetime.fromisoformat(users[user_id]['last_invite'])
        now = datetime.now()
        if (now - last_invite) > timedelta(weeks=1):
            users[user_id]['invites_left'] = 3
        if users[user_id]['invites_left'] > 0:
            expire_date = datetime.now() + timedelta(seconds=10)
            invite_link = await context.bot.create_chat_invite_link(CHANNEL_ID, expire_date=expire_date)
            invite_link = invite_link.invite_link
            users[user_id]['last_invite'] = str(now)
            users[user_id]['invites_left'] -= 1
            save_users(users)
            await update.message.reply_text(f"👉 [Join Channel]({invite_link})", parse_mode='Markdown')
        else:
            await update.message.reply_text("🚫 You have reached your weekly invite limit. Please try again next week.")
    else:
        await update.message.reply_text("❌ You are not verified yet. Please complete the captcha by sending /start.")

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.effective_user.id)
    logger.info(f"Admin panel accessed by user ID: {user_id}")
    if user_id in map(str, ADMIN_IDS):
        keyboard = [
            [InlineKeyboardButton("👤 View Users", callback_data='view_users')],
            [InlineKeyboardButton("♻️ Reset Invites", callback_data='reset_invites')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("⚙️ Admin Panel:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("🚫 You do not have permission to access the admin panel.")
    logger.warning(f"Unauthorized access attempt to admin panel by user ID: {user_id}")

async def admin_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    logger.info(f"Admin action {query.data} accessed by user ID: {user_id}")
    if user_id in map(str, ADMIN_IDS):
        if query.data == 'view_users':
            users_list = '\n'.join([f"{user}: {data}" for user, data in users.items()])
            await query.edit_message_text(f"👥 Users:\n{users_list}")
        elif query.data == 'reset_invites':
            for user in users.values():
                user['invites_left'] = 3
            save_users(users)
            await query.edit_message_text("♻️ Invite limits reset for all users.")
    else:
        await query.edit_message_text("🚫 You do not have permission to perform this action.")
        logger.warning(f"Unauthorized action attempt by user ID: {user_id}")

async def join_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.effective_user.id)
    if user_id in map(str, ADMIN_IDS):
        if update.message.sender_chat and update.message.sender_chat.type == "channel":
            channel_id = update.message.sender_chat.id
            try:
                chat = await context.bot.get_chat(channel_id)  # Ensure the bot can access the chat
                await context.bot.join_chat(chat.id)
                await update.message.reply_text(f"✅ Successfully joined the channel: {chat.title}")
            except Exception as e:
                await update.message.reply_text(f"🚫 Failed to join the channel: {e}")
        elif update.message.text and update.message.text.startswith("https://t.me/"):
            channel_link = update.message.text.strip()
            try:
                chat = await context.bot.get_chat(channel_link)
                await context.bot.join_chat(chat.id)
                await update.message.reply_text(f"✅ Successfully joined the channel: {chat.title}")
            except Exception as e:
                await update.message.reply_text(f"🚫 Failed to join the channel: {e}")
        else:
            await update.message.reply_text("🚫 Please forward a message from a public channel or send a channel link.")
    else:
        await update.message.reply_text("🚫 You do not have permission to perform this action.")
        logger.warning(f"Unauthorized join channel attempt by user ID: {user_id}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.effective_user.id)
    if user_id in map(str, ADMIN_IDS):
        help_text = (
            "ℹ️ *Help Menu*\n\n"
            "👤 *Regular Users:*\n"
            "• /start - Start the verification process\n"
            "• /invite - Generate an invite link (if verified)\n\n"
            "⚙️ *Admins:*\n"
            "• /admin - Open the admin panel"
        )
    else:
        help_text = (
            "ℹ️ *Help Menu*\n\n"
            "👤 *Regular Users:*\n"
            "• /start - Start the verification process\n"
            "• /invite - Generate an invite link (if verified)"
        )
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

def main() -> None:
    """Run the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TOKEN).build()

    # Add conversation handler with the states START, CAPTCHA, and MOVE_RED_SQUARE
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            START: [CallbackQueryHandler(button)],
            CAPTCHA: [CallbackQueryHandler(button)],
            MOVE_RED_SQUARE: [CallbackQueryHandler(move_red_square_button)]
        },
        fallbacks=[CommandHandler("start", start)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("invite", create_invite))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("help", help_command))  # Added help command
    application.add_handler(CallbackQueryHandler(admin_button))
    application.add_handler(MessageHandler(filters.FORWARDED | filters.TEXT, join_channel))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
