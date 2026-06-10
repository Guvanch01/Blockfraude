"""
GuardBot — Professional Telegram Group Protection Bot
Automatically blocks Scam and Sexual content
"""

import logging
import os
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application, MessageHandler, CommandHandler,
    filters, ContextTypes
)
from telegram.constants import ParseMode

from database import Database
from ai_filter import AIFilter
from payments import PaymentManager

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "6581335835").split(",") if x]

db = Database()
ai = AIFilter()
payments = PaymentManager(db)


# ─────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────

async def ban_user(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE, reason: str):
    try:
        await context.bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
        logger.info(f"✅ BANNED user {user_id} | Reason: {reason}")
        return True
    except Exception as e:
        logger.error(f"Ban failed: {e}")
        return False


async def notify_admins(chat_id: int, user_id: int, username: str,
                        reason: str, text_preview: str, context: ContextTypes.DEFAULT_TYPE):
    """Adminlere blok habary (Türkmençe - diňe seniň üçin)"""
    try:
        admins = await context.bot.get_chat_administrators(chat_id)
        msg = (
            f"🚫 <b>New Block Action</b>\n\n"
            f"👤 User: @{username or user_id}\n"
            f"⚠️ Reason: {reason}\n"
            f"💬 Message: <i>{text_preview[:120]}...</i>\n"
            f"🕐 Time: {datetime.now().strftime('%H:%M, %d.%m.%Y')}"
        )
        for admin in admins:
            if not admin.user.is_bot:
                try:
                    await context.bot.send_message(
                        chat_id=admin.user.id,
                        text=msg,
                        parse_mode=ParseMode.HTML
                    )
                except:
                    pass
    except Exception as e:
        logger.error(f"Notify admins error: {e}")


# ─────────────────────────────────────────
# Main Message Handler
# ─────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat:
        return

    chat = update.effective_chat
    user = update.effective_user
    message = update.message

    if chat.type not in ("group", "supergroup"):
        return

    # Group registered and subscription active check
    if not db.get_group(chat.id) or not payments.is_subscription_active(chat.id):
        return

    # Get text from message
    text = message.text or message.caption or ""
    
    # Forwarded message support
    if (getattr(message, 'forward_from', None) or 
        getattr(message, 'forward_from_chat', None) or 
        getattr(message, 'forward_origin', None)):
        text += " [Forwarded message]"

    if len(text.strip()) < 3 and not message.photo and not message.video:
        return

    # Protect admins and group owner
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        if member.status in ("administrator", "creator"):
            return
    except Exception:
        pass

    # AI Analysis
    result = await ai.analyze(text)

    if result.get("is_harmful"):
        reason = result.get("reason", "Harmful content")
        confidence = result.get("confidence", 0.75)
        category = result.get("category", "harmful")

        logger.info(f"🚫 BLOCKED | User: {user.id} | Category: {category} | Reason: {reason}")

        # Delete message
        try:
            await message.delete()
        except Exception as e:
            logger.warning(f"Could not delete message: {e}")

        # Ban user
        banned = await ban_user(chat.id, user.id, context, reason)

        # Log to database
        db.log_action(
            chat_id=chat.id,
            user_id=user.id,
            username=user.username,
            reason=reason,
            confidence=confidence,
            message_preview=text[:150]
        )

        # Notify admins
        if banned:
            await notify_admins(
                chat_id=chat.id,
                user_id=user.id,
                username=user.username or str(user.id),
                reason=reason,
                text_preview=text,
                context=context
            )


# ─────────────────────────────────────────
# Commands (Fully in English)
# ─────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        msg = (
            "👋 <b>Welcome to GuardBot!</b>\n\n"
            "🛡 I automatically protect your groups from scammers and sexual spam.\n\n"
            "📋 <b>How to use:</b>\n"
            "1. Add me to your group as Administrator\n"
            "2. Type /register in the group\n"
            "3. Get 30 days free trial immediately!\n\n"
            "Use /help for all commands."
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text("👋 Please use /register to activate this group.")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "ℹ️ <b>GuardBot Help</b>\n\n"
        "🤖 This bot uses AI to automatically detect and block:\n"
        "• Scam & Fraud messages\n"
        "• Sexual / Adult spam\n\n"
        "📌 <b>Available Commands:</b>\n"
        "/register — Register your group\n"
        "/stats — View ban statistics\n"
        "/status — Check subscription status\n"
        "/pricing — See pricing plans\n"
        "/pay — Payment instructions\n\n"
        "Need support? Contact the developer."
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


async def cmd_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("⚠️ Please use this command inside a group.")
        return

    member = await context.bot.get_chat_member(chat.id, user.id)
    if member.status not in ("administrator", "creator"):
        await update.message.reply_text("🚫 Only group admins can use this command.")
        return

    success = db.register_group(chat.id, chat.title, user.id)
    if success:
        payments.start_free_trial(chat.id)
        await update.message.reply_text(
            f"✅ <b>{chat.title}</b> has been registered successfully!\n\n"
            "🎉 Your 30-day free trial has started.\n"
            "GuardBot is now protecting this group from scams and sexual content.",
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text("⚠️ This group is already registered.")


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("⚠️ Use this command in a group.")
        return

    member = await context.bot.get_chat_member(chat.id, user.id)
    if member.status not in ("administrator", "creator"):
        await update.message.reply_text("🚫 Only admins can view statistics.")
        return

    stats = db.get_stats(chat.id)
    sub = payments.get_subscription_info(chat.id)

    await update.message.reply_text(
        f"📊 <b>Statistics — {chat.title}</b>\n\n"
        f"🚫 Total Banned: {stats['total_bans']}\n"
        f"🔴 Scam: {stats['scam_bans']}\n"
        f"🔞 Sexual: {stats['sexual_bans']}\n\n"
        f"💳 Subscription: {sub['status']}\n"
        f"📅 Expires: {sub['expires_at']}",
        parse_mode=ParseMode.HTML
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        await update.message.reply_text("📌 Please use /status in private chat with the bot.")
        return

    user = update.effective_user
    groups = db.get_user_groups(user.id)

    if not groups:
        await update.message.reply_text("❌ You haven't registered any groups yet.")
        return

    text = "📋 <b>Your Groups:</b>\n\n"
    for g in groups:
        sub = payments.get_subscription_info(g["chat_id"])
        text += f"📌 <b>{g['title']}</b>\n   Status: {sub['status']}\n   Expires: {sub['expires_at']}\n\n"

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_pricing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "💰 <b>GuardBot Pricing</b>\n\n"
        "🎁 Free Trial — 30 days\n\n"
        "📦 Monthly Plans:\n"
        "• Starter — $2/month\n"
        "• Basic — $5/month\n"
        "• Pro — $10/month\n"
        "• Business — $20/month\n"
        "• Enterprise — $45/month\n\n"
        "Use /pay for payment instructions."
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


async def cmd_pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "💳 <b>Payment Instructions</b>\n\n"
        "1. Choose plan → /pricing\n"
        "2. Send payment to our Telegram wallet\n"
        "3. Send screenshot + group link to us\n\n"
        "We will activate your group within 1 hour."
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


# ─────────────────────────────────────────
# Main (Render.com üçin iň dogry wariant)
# ─────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Komandalar
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("register", cmd_register))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("pricing", cmd_pricing))
    app.add_handler(CommandHandler("pay", cmd_pay))

    # Esasy handler
    app.add_handler(MessageHandler(
        (filters.TEXT | filters.CAPTION | filters.PHOTO | filters.VIDEO) & ~filters.COMMAND,
        handle_message
    ))

    logger.info("🚀 GuardBot Professional English Version Started...")

    # Render.com üçin iň amatly we ýönekeý usul
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
