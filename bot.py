"""Telegram Joinhider bot.

Deletes service messages when users join or leave a group.
"""

import logging
import os

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters


logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
)
logger = logging.getLogger("joinhider")


def token_from_environment() -> str:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is missing. Create a bot with @BotFather and set the token."
        )
    return token


async def delete_service_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Delete a join/leave service message when Telegram permits it."""
    message = update.effective_message
    if message is None:
        return

    try:
        await message.delete()
        logger.info("Deleted join/leave message %s in chat %s", message.message_id, message.chat_id)
    except Exception:
        # Missing delete permission, old message, or another Telegram API restriction
        # should not stop the bot from handling future messages.
        logger.exception(
            "Could not delete message %s in chat %s; check admin permissions",
            message.message_id,
            message.chat_id,
        )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Explain how to enable the bot in a group."""
    if update.effective_message:
        await update.effective_message.reply_text(
            "Joinhider is ready. Add me to your group, make me an administrator "
            "with Delete messages permission, and I will hide join/leave notices."
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show setup instructions in Telegram."""
    if update.effective_message:
        await update.effective_message.reply_text(
            "Setup:\n"
            "1. Add me to your group.\n"
            "2. Promote me to administrator.\n"
            "3. Enable Delete messages.\n\n"
            "I work independently in every group where I am added."
        )


def build_application() -> Application:
    application = Application.builder().token(token_from_environment()).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    service_message_filter = filters.StatusUpdate.NEW_CHAT_MEMBERS | filters.StatusUpdate.LEFT_CHAT_MEMBER
    application.add_handler(MessageHandler(service_message_filter, delete_service_message))
    return application


if __name__ == "__main__":
    logger.info("Starting Joinhider bot")
    build_application().run_polling(allowed_updates=Update.ALL_TYPES)
