import logging
import os
import sqlite3
from datetime import datetime, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
)
logger = logging.getLogger("vip_payment_bot")

DB_PATH = os.getenv("DB_PATH", "payments.db")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
VIP_CHANNEL_ID = int(os.getenv("VIP_CHANNEL_ID", "0"))
VIP_CHANNEL_USERNAME = os.getenv("VIP_CHANNEL_USERNAME", "").strip()
PAYMENT_NAME = os.getenv("PAYMENT_NAME", "YOUR NAME")
PAYMENT_NUMBER = os.getenv("PAYMENT_NUMBER", "98XXXXXXXX")
PAYMENT_AMOUNT = os.getenv("PAYMENT_AMOUNT", "500")
VIP_TITLE = os.getenv("VIP_TITLE", "VIP CHANNEL")


def token_from_environment() -> str:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing.")
    return token


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            name TEXT,
            proof_file_id TEXT,
            proof_type TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            reviewed_at TEXT
        )"""
    )
    conn.commit()
    return conn


def save_payment(user_id, username, name, file_id, file_type):
    conn = db()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO payments
        (user_id, username, name, proof_file_id, proof_type, status, created_at)
        VALUES (?, ?, ?, ?, ?, 'pending', ?)""",
        (
            user_id,
            username or "",
            name or "",
            file_id,
            file_type,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    payment_id = cur.lastrowid
    conn.commit()
    conn.close()
    return payment_id


def update_status(payment_id, status):
    conn = db()
    conn.execute(
        "UPDATE payments SET status=?, reviewed_at=? WHERE id=?",
        (status, datetime.now(timezone.utc).isoformat(), payment_id),
    )
    conn.commit()
    conn.close()


def get_payment(payment_id):
    conn = db()
    row = conn.execute(
        "SELECT id,user_id,username,name,status FROM payments WHERE id=?",
        (payment_id,),
    ).fetchone()
    conn.close()
    return row


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.effective_message:
        return

    keyboard = [
        [InlineKeyboardButton("💳 PAYMENT DETAILS", callback_data="payment_details")],
        [InlineKeyboardButton("📤 SEND PAYMENT PROOF", callback_data="send_proof")],
        [InlineKeyboardButton("🔎 CHECK STATUS", callback_data="check_status")],
    ]
    await update.effective_message.reply_text(
        f"🔐 {VIP_TITLE}\n\n"
        "VIP channel join गर्नुअघि payment verify गर्नुपर्छ।\n\n"
        f"💰 Amount: {PAYMENT_AMOUNT}\n"
        "पहिले payment गर्नुहोस्, त्यसपछि screenshot पठाउनुहोस्।\n"
        "Admin approval भएपछि मात्र VIP join link दिइनेछ।",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def payment_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        f"💳 PAYMENT DETAILS\n\n"
        f"👤 Name: {PAYMENT_NAME}\n"
        f"📱 Account/Number: {PAYMENT_NUMBER}\n"
        f"💰 Amount: {PAYMENT_AMOUNT}\n\n"
        "Payment गरेपछि तलको SEND PAYMENT PROOF बाट screenshot पठाउनुहोस्।",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("📤 SEND PAYMENT PROOF", callback_data="send_proof")]]
        ),
    )


async def send_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["awaiting_proof"] = True
    await q.message.reply_text(
        "📤 Payment proof पठाउनुहोस्।\n\n"
        "Payment screenshot/photo पठाउनुहोस्।\n"
        "Caption मा Transaction ID पनि लेख्न सक्नुहुन्छ।"
    )


async def check_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    conn = db()
    row = conn.execute(
        "SELECT status FROM payments WHERE user_id=? ORDER BY id DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    conn.close()

    status = row[0] if row else "none"
    if status == "approved":
        await q.message.reply_text("✅ Payment approved छ। /join पठाएर VIP channel link लिनुहोस्।")
    elif status == "pending":
        await q.message.reply_text("⏳ तपाईंको payment proof admin review मा छ।")
    elif status == "rejected":
        await q.message.reply_text("❌ Payment reject भएको छ। फेरि valid proof पठाउनुहोस्।")
    else:
        await q.message.reply_text("ℹ️ Payment proof भेटिएन।")


async def receive_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.effective_message:
        return
    if not context.user_data.get("awaiting_proof"):
        return

    message = update.effective_message
    file_id = None
    file_type = None

    if message.photo:
        file_id = message.photo[-1].file_id
        file_type = "photo"
    elif message.document:
        file_id = message.document.file_id
        file_type = "document"
    else:
        await message.reply_text("❗ कृपया payment screenshot/photo पठाउनुहोस्।")
        return

    context.user_data["awaiting_proof"] = False
    payment_id = save_payment(
        update.effective_user.id,
        update.effective_user.username,
        update.effective_user.full_name,
        file_id,
        file_type,
    )

    await message.reply_text(
        f"📨 Proof received!\n\n"
        f"🆔 Request #{payment_id}\n"
        "⏳ Admin verification हुँदैछ। Approval भएपछि VIP join link प्राप्त हुनेछ।"
    )

    if ADMIN_ID:
        buttons = InlineKeyboardMarkup(
            [[
                InlineKeyboardButton("✅ APPROVE", callback_data=f"approve:{payment_id}"),
                InlineKeyboardButton("❌ REJECT", callback_data=f"reject:{payment_id}"),
            ]]
        )
        caption = (
            f"💳 NEW PAYMENT #{payment_id}\n"
            f"👤 {update.effective_user.full_name}\n"
            f"🆔 User ID: {update.effective_user.id}\n"
            f"🔗 @{update.effective_user.username or 'no_username'}"
        )
        if file_type == "photo":
            await context.bot.send_photo(
                ADMIN_ID, file_id, caption=caption, reply_markup=buttons
            )
        else:
            await context.bot.send_document(
                ADMIN_ID, file_id, caption=caption, reply_markup=buttons
            )


async def review_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.from_user.id != ADMIN_ID:
        await q.answer("⛔ Admin only.", show_alert=True)
        return

    action, payment_id_text = q.data.split(":")
    payment_id = int(payment_id_text)
    row = get_payment(payment_id)

    if not row:
        await q.message.reply_text("❌ Payment request not found.")
        return

    _, user_id, username, name, status = row

    if status != "pending":
        await q.message.reply_text(f"ℹ️ Request #{payment_id} already {status}.")
        return

    if action == "reject":
        update_status(payment_id, "rejected")
        await context.bot.send_message(
            user_id,
            f"❌ Payment request #{payment_id} rejected भएको छ।\n"
            "Valid payment proof पठाएर फेरि try गर्नुहोस्।",
        )
        await q.message.edit_caption(
            caption=(q.message.caption or "") + "\n\n❌ REJECTED"
        )
        return

    if action == "approve":
        update_status(payment_id, "approved")
        await context.bot.send_message(
            user_id,
            f"✅ Payment #{payment_id} APPROVED!\n\n"
            "अब /join पठाएर VIP channel join link लिनुहोस्।",
        )
        await q.message.edit_caption(
            caption=(q.message.caption or "") + "\n\n✅ APPROVED"
        )


async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.effective_message:
        return

    conn = db()
    row = conn.execute(
        "SELECT status FROM payments WHERE user_id=? ORDER BY id DESC LIMIT 1",
        (update.effective_user.id,),
    ).fetchone()
    conn.close()

    if not row or row[0] != "approved":
        await update.effective_message.reply_text(
            "🔒 VIP channel locked छ।\n\n"
            "पहिले payment गर्नुहोस् र admin बाट approval लिनुहोस्।"
        )
        return

    if not VIP_CHANNEL_ID:
        await update.effective_message.reply_text(
            "⚠️ VIP_CHANNEL_ID configure गरिएको छैन। Admin ले bot settings पूरा गर्नुपर्छ।"
        )
        return

    try:
        invite = await context.bot.create_chat_invite_link(
            chat_id=VIP_CHANNEL_ID,
            name=f"VIP-{update.effective_user.id}",
            member_limit=1,
        )
        await update.effective_message.reply_text(
            "🎉 Payment verified!\n\n"
            "🔐 Your VIP channel join link:\n"
            f"{invite.invite_link}\n\n"
            "⚠️ यो link तपाईंका लागि मात्र हो।"
        )
    except Exception:
        logger.exception("Could not create VIP invite link")
        await update.effective_message.reply_text(
            "❌ VIP invite link बनाउन सकिएन। Bot लाई channel मा admin बनाएर "
            "Invite Users permission दिनुहोस्।"
        )


async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or update.effective_user.id != ADMIN_ID:
        await update.effective_message.reply_text("⛔ Admin only.")
        return

    conn = db()
    pending = conn.execute(
        "SELECT COUNT(*) FROM payments WHERE status='pending'"
    ).fetchone()[0]
    approved = conn.execute(
        "SELECT COUNT(*) FROM payments WHERE status='approved'"
    ).fetchone()[0]
    rejected = conn.execute(
        "SELECT COUNT(*) FROM payments WHERE status='rejected'"
    ).fetchone()[0]
    conn.close()

    await update.effective_message.reply_text(
        "👑 ADMIN PANEL\n\n"
        f"⏳ Pending: {pending}\n"
        f"✅ Approved: {approved}\n"
        f"❌ Rejected: {rejected}\n\n"
        "New payment proof आएपछि यहीँ Approve/Reject button देखिन्छ।"
    )


def main():
    db()
    app = Application.builder().token(token_from_environment()).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("join", join))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CallbackQueryHandler(payment_details, pattern="^payment_details$"))
    app.add_handler(CallbackQueryHandler(send_proof, pattern="^send_proof$"))
    app.add_handler(CallbackQueryHandler(check_status, pattern="^check_status$"))
    app.add_handler(CallbackQueryHandler(review_payment, pattern="^(approve|reject):\\d+$"))
    app.add_handler(
        MessageHandler(
            (filters.PHOTO | filters.Document.ALL) & ~filters.COMMAND,
            receive_proof,
        )
    )

    logger.info("Starting VIP Payment Verify Bot")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
