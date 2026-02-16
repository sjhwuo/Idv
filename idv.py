import logging
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from telegram.error import BadRequest, Forbidden

# ========== НАСТРОЙКИ ==========
TOKEN = "8372962296:AAFr8dMSqOCwhP_wRK1kHVWnhjEwlfJyH0k"   # токен бота
ADMINS = [5568161397, 1662341251]  # список админов


# Состояния
WAITING_REPLY = 1

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ====== /start ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📤 Отправить заявку", callback_data="send_data")],
        [InlineKeyboardButton("ℹ️ Инфо флуда", callback_data="info")],
        [InlineKeyboardButton("👮 Администрация", callback_data="admin")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # боковое меню
    side_menu = ReplyKeyboardMarkup(
        [["/start", "/info", "/admin"]],
        resize_keyboard=True
    )

    await update.message.reply_text(
        "Снова Здравствуй! Наш флуд имеет ограничение по возрасту 14+.\n\n"
        "Для вступления требуется:\n"
        "1) Роль, которую вы хотите занять\n"
        "2) Ваш юзер (@example)\n\n"
        "Администрация постарается обработать ваш запрос как можно скорее.",
        reply_markup=reply_markup,
    )

    # прикрепляем меню с невидимым символом
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="\u200B",
        reply_markup=side_menu
    )


# ====== Общие кнопки (info/admin/send_data) ======
async def general_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data or ""
    try:
        await query.answer()
    except Exception:
        pass

    if data == "send_data":
        context.user_data["waiting_for_application"] = True
        await query.message.reply_text(
            "📌 Пожалуйста, напишите роль и ваш юзер.\n\n"
            "После этого бот автоматически отправит заявку администрации."
        )
    elif data == "info":
        await query.message.reply_text("Наше инфо! https://t.me/infoboedelya")
    elif data == "admin":
        await query.message.reply_text(
            "Связь с администрацией:\nВладелец — @sjhwuo\nГл.Админ — @subemeow"
        )


# ====== Обработка входящих сообщений от пользователей ======
async def user_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user and update.effective_user.id in ADMINS:
        return

    if not context.user_data.get("waiting_for_application"):
        await update.message.reply_text("⚠️ Сначала нажмите кнопку «📤 Отправить заявку».")
        return

    user = update.effective_user
    username = f"@{user.username}" if user.username else "(без username)"
    user_id = user.id

    header = f"📩 Новая заявка от {username} (ID: {user_id})"
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("✉️ Ответить", callback_data=f"reply_{user_id}")]]
    )

    delivered = False
    try:
        if update.message.photo:
            file_id = update.message.photo[-1].file_id
            caption = f"{header}\n\nСообщение: {update.message.caption or ''}"
            for admin_id in ADMINS:
                await context.bot.send_photo(
                    chat_id=admin_id, photo=file_id, caption=caption, reply_markup=kb
                )
            delivered = True
        elif update.message.text:
            text = f"{header}\n\nСообщение: {update.message.text}"
            for admin_id in ADMINS:
                await context.bot.send_message(chat_id=admin_id, text=text, reply_markup=kb)
            delivered = True
        else:
            for admin_id in ADMINS:
                await context.bot.forward_message(
                    chat_id=admin_id,
                    from_chat_id=update.message.chat_id,
                    message_id=update.message.message_id,
                )
                await context.bot.send_message(chat_id=admin_id, text=header, reply_markup=kb)
            delivered = True

        if delivered:
            await update.message.reply_text("✅ Ваша заявка отправлена администрации.")
            context.user_data["waiting_for_application"] = False

    except (BadRequest, Forbidden) as e:
        logger.error(f"Ошибка при пересылке админу: {e}")
        try:
            await update.message.reply_text("⚠️ Не удалось доставить заявку администрации. Попробуйте позже.")
        except Exception:
            pass


# ====== Callback: кнопка "Ответить" ======
async def reply_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data or ""
    try:
        await query.answer()
    except Exception:
        pass

    if not data.startswith("reply_"):
        await query.message.reply_text("Неверный callback.")
        return ConversationHandler.END

    try:
        target_id = int(data.split("_", 1)[1])
    except Exception:
        await query.message.reply_text("Не удалось определить ID пользователя.")
        return ConversationHandler.END

    context.user_data["reply_to_user_id"] = target_id
    await query.message.reply_text(f"✍️ Введите сообщение — оно будет отправлено пользователю ID: {target_id}")
    return WAITING_REPLY


# ====== Отправка ответа от админа ======
async def admin_send_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMINS:
        await update.message.reply_text("⛔️ У вас нет прав отправлять ответы.")
        return ConversationHandler.END

    target_id = context.user_data.get("reply_to_user_id")
    if not target_id:
        await update.message.reply_text("❌ Цель не найдена. Нажмите кнопку Ответить у заявки заново.")
        return ConversationHandler.END

    text = update.message.text or ""
    try:
        await context.bot.send_message(chat_id=target_id, text=f"📩 Ответ администрации:\n\n{text}")
        await update.message.reply_text("✅ Ответ отправлен пользователю.")
        logger.info(f"Админ {update.effective_user.id} ответил пользователю {target_id}")
    except Exception as e:
        logger.error(f"Ошибка при отправке ответа пользователю {target_id}: {e}")
        await update.message.reply_text(f"❌ Не удалось отправить сообщение пользователю: {e}")

    context.user_data.pop("reply_to_user_id", None)
    return ConversationHandler.END


# ====== Ошибки ======
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Ошибка при обработке апдейта:", exc_info=context.error)


# ====== MAIN ======
def main():
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(reply_button_callback, pattern=r"^reply_\d+$")],
        states={
            WAITING_REPLY: [
                MessageHandler(
                    filters.TEXT & filters.User(ADMINS) & ~filters.COMMAND,
                    admin_send_reply,
                )
            ],
        },
        fallbacks=[],
        allow_reentry=True,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("info", lambda u, c: u.message.reply_text("Наше инфо! https://t.me/infoboedelya")))
    app.add_handler(CommandHandler("admin", lambda u, c: u.message.reply_text("Связь с администрацией:\nВладелец — @sjhwuo\nГл.Админ — @subemeow")))
    app.add_handler(CallbackQueryHandler(general_callback_handler, pattern=r"^(send_data|info|admin)$"))
    app.add_handler(conv)
    app.add_handler(MessageHandler(filters.ALL & ~filters.User(ADMINS), user_message_handler))
    app.add_error_handler(error_handler)

    app.run_polling()


if __name__ == "__main__":
    main()