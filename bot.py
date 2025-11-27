import random
from datetime import datetime
from telegram.constants import ParseMode
from telegram import (
    Update, KeyboardButton, ReplyKeyboardMarkup,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters, ConversationHandler
)

from CATEGORIES import CATEGORIES

# === Sozlamalar ===
CONFIG = {
    "GROUP_ID": -1002975206328,  # Guruh ID
    "TOKEN": "8516892080:AAGcPCWZkGQRHPf2SyWsM8r7cPIMLY8AdW8",  # !!! Haqiqiy tokenni bu yerga vaqtincha yozing, keyin yashirganing ma'qul
    "MAX_ORDER_QUANTITY": 15,
    "MIN_ORDER_AMOUNT": 155000,   # Minimal umumiy summa
    "WORKING_HOURS": {            # Ish vaqti (local server soatiga qarab)
        "start": 9,   # 09:00 dan
        "end": 21     # 21:00 gacha
    }
}

# === Bosqichlar ===
ASK_PROFILE_CONFIRM, ASK_PHONE, ASK_COMMENT = range(3)

# === User profillari (RAMda, bot o‘chsa — o‘chadi) ===
# user_id: {"phone": "...", "comment": "..."}
USER_PROFILES = {}


# === Buyurtma ID generatori ===
def generate_order_id():
    return f"#{random.randint(1000, 9999)}"


# === Kategoriyalarni yuklash ===
def load_categories():
    return CATEGORIES


# === User tilini olish ===
def get_lang(context: ContextTypes.DEFAULT_TYPE) -> str:
    return context.user_data.get("lang", "uz")


# === Asosiy menyuni ko‘rsatish (tilga qarab) ===
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)

    if lang == "ru":
        kb = ReplyKeyboardMarkup(
            [
                [KeyboardButton("🛒 Сделать заказ")],
                [KeyboardButton("📂 Меню (каталог)")],
                [KeyboardButton("🧺 Корзина")],
                [KeyboardButton("❌ Отмена")]
            ],
            resize_keyboard=True
        )
        text = "👋 Здравствуйте!\nВыберите действие ниже 👇"
    else:
        kb = ReplyKeyboardMarkup(
            [
                [KeyboardButton("🛒 Buyurtma berish")],
                [KeyboardButton("📂 Menyu (katalog)")],
                [KeyboardButton("🧺 Savatni ko‘rish")],
                [KeyboardButton("❌ Bekor qilish")]
            ],
            resize_keyboard=True
        )
        text = "👋 Assalomu alaykum!\nMenyu yoki buyurtma berishni tanlang 👇"

    context.user_data.setdefault("cart", {})
    context.user_data.pop("in_order_process", None)

    await update.message.reply_text(text, reply_markup=kb)


# === Start (til tanlash yoki menyu) ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Agar til tanlanmagan bo‘lsa — avval tilni tanlatamiz
    if "lang" not in context.user_data:
        kb = ReplyKeyboardMarkup(
            [
                [KeyboardButton("🇺🇿 O‘zbek"), KeyboardButton("🇷🇺 Русский")]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await update.message.reply_text(
            "Tilni tanlang / Выберите язык:",
            reply_markup=kb
        )
        return

    # Til tanlangan bo‘lsa — asosiy menyuni ko‘rsatamiz
    await show_main_menu(update, context)


# === Til tanlash handleri ===
async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if "O‘zbek" in text or "O'zbek" in text:
        context.user_data["lang"] = "uz"
    elif "Русский" in text:
        context.user_data["lang"] = "ru"
    else:
        # Bu boshqa matn bo‘lsa — e’tibor bermaymiz
        return

    # Til tanlangach asosiy menyu
    await show_main_menu(update, context)


# === Har qanday yozuvni qabul qilish ===
async def any_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Buyurtma jarayoni bo‘lmasa -> menyuni chiqaradi.
    Agar hozir buyurtma jarayonida bo‘lsa, bu handler aralashmaydi.
    """
    if context.user_data.get("in_order_process"):
        return

    # Agar til hali tanlanmagan bo‘lsa, start funksiyasini chaqiramiz
    if "lang" not in context.user_data:
        await start(update, context)
    else:
        await show_main_menu(update, context)


# === Katalogni ko‘rsatish ===
async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    categories = load_categories()
    kb = [[InlineKeyboardButton(cat, callback_data=f"cat|{cat}")] for cat in categories.keys()]

    lang = get_lang(context)
    if lang == "ru":
        text = "📂 Выберите раздел каталога:"
    else:
        text = "📂 Katalog bo‘limini tanlang:"

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(kb)
    )


# === Mahsulotlarni ko‘rsatish (1–15 dona tanlash tugmalari bilan) ===
async def show_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, category = query.data.split("|")
    categories = load_categories()
    products = categories.get(category)

    if not products:
        await query.message.reply_text("❌ Kategoriyada mahsulotlar topilmadi.")
        return

    for name, info in products.items():
        # 1–15 gacha bo'lgan sonli tugmalarni yasaymiz
        rows = [
            range(1, 6),    # 1 2 3 4 5
            range(6, 11),   # 6 7 8 9 10
            range(11, 16),  # 11 12 13 14 15
        ]
        kb_rows = []
        for row in rows:
            kb_rows.append([
                InlineKeyboardButton(
                    str(i),
                    callback_data=f"qty|{name}|{i}"
                )
                for i in row
            ])

        # 0 qilish (savatdan o‘chirish) tugmasi
        kb_rows.append([
            InlineKeyboardButton("🗑 O‘chirish", callback_data=f"qty|{name}|0")
        ])

        btn = InlineKeyboardMarkup(kb_rows)

        await query.message.reply_photo(
            photo=info["img"],
            caption=f"{name}\n💵 Narxi: {info['price']} so‘m\n📦 Soni: 0 ta",
            reply_markup=btn
        )


# === Mahsulot narxini olish ===
def get_product_price(product_name):
    categories = load_categories()
    for category in categories.values():
        if product_name in category:
            return category[product_name]["price"]
    return 0


# === Savatni formatlash ===
def format_cart(cart):
    if not cart:
        return "❌ Savat bo‘sh"
    items, total = [], 0
    for product, qty in cart.items():
        price = get_product_price(product) * qty
        total += price
        items.append(f"{product} x{qty} = {price} so‘m")
    return "\n".join(items) + f"\n\n💵 Umumiy summa: {total} so‘m"


# === 🧺 Savatni ko‘rsatish ===
async def show_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cart = context.user_data.get("cart", {})
    lang = get_lang(context)

    if not cart:
        if lang == "ru":
            text = "❌ Ваша корзина пуста."
        else:
            text = "❌ Savatingiz hozircha bo‘sh."
        await update.message.reply_text(text)
        return

    cart_text = format_cart(cart)
    if lang == "ru":
        prefix = "🧺 Ваша корзина:\n"
    else:
        prefix = "🧺 Savatingiz:\n"
    await update.message.reply_text(prefix + cart_text)


# === Savatni yangilash (qty|mahsulot|son) ===
async def update_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    parts = query.data.split("|")
    action = parts[0]

    # Faqat qty callbacklarini qayta ishlaymiz
    if action != "qty":
        return

    product_name = parts[1]
    try:
        requested_qty = int(parts[2])
    except (IndexError, ValueError):
        requested_qty = 0

    cart = context.user_data.setdefault("cart", {})

    # 0 bo‘lsa – savatdan o‘chirib tashlaymiz
    if requested_qty <= 0:
        if product_name in cart:
            del cart[product_name]
    else:
        # Maksimal 15 taga cheklaymiz
        if requested_qty > CONFIG["MAX_ORDER_QUANTITY"]:
            requested_qty = CONFIG["MAX_ORDER_QUANTITY"]
            await query.answer(
                f"❗ Maksimum {CONFIG['MAX_ORDER_QUANTITY']} ta bo‘lishi mumkin",
                show_alert=True
            )
        cart[product_name] = requested_qty

    price = get_product_price(product_name)
    qty = cart.get(product_name, 0)
    new_caption = (
        f"{product_name}\n"
        f"💵 Narxi: {price} so‘m\n"
        f"📦 Soni: {qty} ta"
    )

    # Tugmalarni qayta yasaymiz (1–15 + o‘chirish)
    rows = [
        range(1, 6),
        range(6, 11),
        range(11, 16),
    ]
    kb_rows = []
    for row in rows:
        kb_rows.append([
            InlineKeyboardButton(
                str(i),
                callback_data=f"qty|{product_name}|{i}"
            )
            for i in row
        ])
    kb_rows.append([
        InlineKeyboardButton("🗑 O‘chirish", callback_data=f"qty|{product_name}|0")
    ])
    btn = InlineKeyboardMarkup(kb_rows)

    try:
        await query.message.edit_caption(
            caption=new_caption,
            reply_markup=btn
        )
    except Exception as e:
        print("❌ Xabarni yangilashda xatolik:", e)


# === Ish vaqti tekshiruv ===
def is_work_time() -> bool:
    now = datetime.now()
    h = now.hour
    return CONFIG["WORKING_HOURS"]["start"] <= h < CONFIG["WORKING_HOURS"]["end"]


# === Buyurtma yakunlash (savatdan keyingi bosqich) ===
async def order_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    cart = context.user_data.get("cart", {})

    if not cart:
        if lang == "ru":
            msg = "❌ Ваша корзина пуста! Сначала выберите товары из меню."
        else:
            msg = "❌ Savatingiz bo‘sh! Avval menyudan mahsulot tanlang."
        await update.message.reply_text(msg)
        return ConversationHandler.END

    # === Ish vaqti tekshiruv ===
    if not is_work_time():
        if lang == "ru":
            text = (
                "⏰ Сейчас время вне рабочего графика.\n\n"
                "Заказы принимаются с 09:00 до 21:00.\n"
                "Ваш заказ можете оформить в это время."
            )
        else:
            text = (
                "⏰ Hozir buyurtma qabul qilish vaqtidan tashqarida.\n\n"
                "Buyurtmalar 09:00 dan 21:00 gacha qabul qilinadi.\n"
                "Iltimos, shu vaqtda buyurtma qoldiring."
            )
        await update.message.reply_text(text)
        return ConversationHandler.END

    # === Minimal summa tekshiruvi ===
    total = sum(get_product_price(p) * q for p, q in cart.items())
    if total < CONFIG["MIN_ORDER_AMOUNT"]:
        if lang == "ru":
            msg = (
                f"⚠️ Минимальная сумма заказа: {CONFIG['MIN_ORDER_AMOUNT']:,} сум.\n"
                f"Ваша корзина: {total:,} сум.\n"
                f"❗ Пожалуйста, добавьте ещё товары."
            )
        else:
            msg = (
                f"⚠️ Minimal buyurtma summasi: {CONFIG['MIN_ORDER_AMOUNT']:,} so‘m\n"
                f"Sizning savatingiz: {total:,} so‘m\n"
                f"❗ Iltimos, yana mahsulot qo‘shing."
            )
        await update.message.reply_text(msg)
        return ConversationHandler.END

    user = update.effective_user
    profile = USER_PROFILES.get(user.id)

    # === Profil mavjud bo‘lsa — tasdiqlatamiz ===
    if profile:
        phone = profile.get("phone", "—")
        comment = profile.get("comment", "—")

        if lang == "ru":
            text = (
                "📁 В вашем профиле сохранены данные:\n\n"
                f"📱 Телефон: {phone}\n"
                f"🏪 Магазин/адрес: {comment}\n\n"
                "Использовать эти данные для нового заказа?"
            )
            kb = ReplyKeyboardMarkup(
                [
                    [KeyboardButton("✅ Подтвердить"), KeyboardButton("✏️ Изменить данные")],
                    [KeyboardButton("❌ Отмена")]
                ],
                resize_keyboard=True,
                one_time_keyboard=True
            )
        else:
            text = (
                "📁 Profilingizda saqlangan ma'lumotlar:\n\n"
                f"📱 Telefon: {phone}\n"
                f"🏪 Do‘kon/manzil: {comment}\n\n"
                "Shu ma'lumotlar bilan buyurtma berasizmi?"
            )
            kb = ReplyKeyboardMarkup(
                [
                    [KeyboardButton("✅ Tasdiqlash"), KeyboardButton("✏️ Ma'lumotlarni o‘zgartirish")],
                    [KeyboardButton("❌ Bekor qilish")]
                ],
                resize_keyboard=True,
                one_time_keyboard=True
            )

        context.user_data["in_order_process"] = False
        await update.message.reply_text(text, reply_markup=kb)
        return ASK_PROFILE_CONFIRM

    # === Agar profil bo‘lmasa — odatdagi jarayon: telefon so‘raymiz ===
    context.user_data["in_order_process"] = True

    cart_text = format_cart(cart)
    if lang == "ru":
        text = (
            f"📦 Ваша корзина:\n{cart_text}\n\n"
            "📱 Отправьте, пожалуйста, номер телефона:"
        )
        kb = ReplyKeyboardMarkup(
            [
                [KeyboardButton("📲 Отправить номер телефона", request_contact=True)],
                [KeyboardButton("❌ Отмена")]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        )
    else:
        text = (
            f"📦 Savatingiz:\n{cart_text}\n\n"
            "📱 Telefon raqamingizni yuboring:"
        )
        kb = ReplyKeyboardMarkup(
            [
                [KeyboardButton("📲 Telefon raqamni yuborish", request_contact=True)],
                [KeyboardButton("❌ Bekor qilish")]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        )

    await update.message.reply_text(text, reply_markup=kb)
    return ASK_PHONE


# === Profilni tasdiqlash/yangi kiritish ===
async def profile_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    user = update.effective_user
    text = update.message.text

    profile = USER_PROFILES.get(user.id)
    if not profile:
        # Teoretik jihatdan bo‘lmasligi kerak, lekin baribir tekshiramiz
        return await order_finish(update, context)

    # Uzbek tugmalar
    uz_confirm = "✅ Tasdiqlash"
    uz_change = "✏️ Ma'lumotlarni o‘zgartirish"
    uz_cancel = "❌ Bekor qilish"
    # Russian tugmalar
    ru_confirm = "✅ Подтвердить"
    ru_change = "✏️ Изменить данные"
    ru_cancel = "❌ Отмена"

    # Bekor qilish
    if text in (uz_cancel, ru_cancel):
        return await cancel(update, context)

    # Tasdiqlash
    if text in (uz_confirm, ru_confirm):
        context.user_data["phone_number"] = profile.get("phone")
        context.user_data["in_order_process"] = True

        prev_comment = profile.get("comment") or ""
        if lang == "ru":
            msg = "✍️ Напишите, пожалуйста, комментарий или адрес.\n"
            if prev_comment:
                msg += f"\n(Ранее вы писали: «{prev_comment}»)"
        else:
            msg = "✍️ Iltimos, qo‘shimcha izoh yoki manzil yozib yuboring.\n"
            if prev_comment:
                msg += f"\n(Oldingi safar yozganingiz: «{prev_comment}»)"

        kb = ReplyKeyboardMarkup(
            [[KeyboardButton("❌ Bekor qilish" if lang == "uz" else "❌ Отмена")]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await update.message.reply_text(msg, reply_markup=kb)
        return ASK_COMMENT

    # Ma'lumotlarni o‘zgartirish — odatdagi telefon jarayoniga qaytamiz
    if lang == "ru":
        msg = "📱 Отправьте, пожалуйста, новый номер телефона:"
        kb = ReplyKeyboardMarkup(
            [
                [KeyboardButton("📲 Отправить номер телефона", request_contact=True)],
                [KeyboardButton("❌ Отмена")]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        )
    else:
        msg = "📱 Yangi telefon raqamingizni yuboring:"
        kb = ReplyKeyboardMarkup(
            [
                [KeyboardButton("📲 Telefon raqamni yuborish", request_contact=True)],
                [KeyboardButton("❌ Bekor qilish")]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        )

    context.user_data["in_order_process"] = True
    await update.message.reply_text(msg, reply_markup=kb)
    return ASK_PHONE


# === Telefonni qabul qilish (contact yoki oddiy matn) ===
async def phone_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    phone_number = None

    if update.message.contact:
        phone_number = update.message.contact.phone_number
    else:
        phone_number = update.message.text.strip()

    context.user_data["phone_number"] = phone_number

    if lang == "ru":
        text = (
            "✍️ Напишите, пожалуйста, комментарий или адрес.\n"
            "✍️ Пожалуйста, также укажите название вашего магазина!"
        )
        kb = ReplyKeyboardMarkup(
            [[KeyboardButton("❌ Отмена")]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
    else:
        text = (
            "✍️ Iltimos, qo‘shimcha izoh yoki manzil yozib yuboring:\n"
            "✍️ Iltimos, do'kongiz nomini ham yozib qoldiring!"
        )
        kb = ReplyKeyboardMarkup(
            [[KeyboardButton("❌ Bekor qilish")]],
            resize_keyboard=True,
            one_time_keyboard=True
        )

    await update.message.reply_text(text, reply_markup=kb)
    return ASK_COMMENT


# === Kommentariya qabul qilish ===
async def comment_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    comment = update.message.text
    user = update.effective_user
    order_id = generate_order_id()
    cart = context.user_data.get("cart", {})
    total = sum(get_product_price(p) * q for p, q in cart.items())
    phone_number = context.user_data.get("phone_number")

    # === Profilni saqlaymiz ===
    USER_PROFILES[user.id] = {
        "phone": phone_number,
        "comment": comment
    }

    if lang == "ru":
        text = (
            f"✅ Ваш заказ принят!\n🆔 Номер заказа: {order_id}\n"
            f"💵 Общая сумма: {total} сум.\n"
            "Оператор свяжется с вами в ближайшее время.\n"
            "Доставка будет осуществлена завтра."
        )
    else:
        text = (
            f"✅ Buyurtmangiz qabul qilindi!\n🆔 Buyurtma raqami: {order_id}\n"
            f"💵 Umumiy summa: {total} so‘m\n"
            f"Operatorlar tez orada bog‘lanadi.\n"
            f"Buyurtmangizni ertaga yetkazib borishadi."
        )

    await update.message.reply_text(text)

    cart_text = "\n".join([f"{p} x{q}" for p, q in cart.items()])
    msg = (
        f"📩 <b>Yangi buyurtma!</b>\n\n"
        f"🆔 ID: {order_id}\n"
        f"👤 Mijoz: {user.first_name} (@{user.username if user.username else 'yo‘q'})\n"
        f"📱 Telefon: {phone_number}\n"
        f"🛒 Savat:\n{cart_text}\n"
        f"💵 Umumiy summa: {total} so‘m\n"
        f"📝 Izoh: {comment}"
    )

    await context.bot.send_message(
        chat_id=CONFIG["GROUP_ID"],
        text=msg,
        parse_mode=ParseMode.HTML
    )

    # Hammasini tozalaymiz
    context.user_data.clear()
    # Yangi buyurtma uchun boshidan, lekin til saqlanmay qolmasin:
    context.user_data["lang"] = get_lang(context)
    await show_main_menu(update, context)
    return ConversationHandler.END


# === Bekor qilish ===
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)

    if lang == "ru":
        text = "❌ Заказ отменён. Вы вернулись в главное меню."
    else:
        text = "❌ Buyurtma bekor qilindi. Asosiy menyuga qaytdingiz."

    context.user_data.clear()
    context.user_data["lang"] = lang
    await update.message.reply_text(text)
    await show_main_menu(update, context)
    return ConversationHandler.END


# === Botni ishga tushirish ===
def main():
    app = ApplicationBuilder().token(CONFIG["TOKEN"]).build()

    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🛒 Buyurtma berish$"), order_finish),
            MessageHandler(filters.Regex("^🛒 Сделать заказ$"), order_finish),
        ],
        states={
            ASK_PROFILE_CONFIRM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, profile_confirm)
            ],
            # Telefon raqam: contact yoki text bo‘lishi mumkin
            ASK_PHONE: [
                MessageHandler(filters.CONTACT | (filters.TEXT & ~filters.COMMAND), phone_receive)
            ],
            ASK_COMMENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, comment_receive)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
            MessageHandler(filters.Regex("^❌ Отмена$"), cancel),
        ],
    )

    # /start va /lang
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("lang", start))

    # Til tanlash tugmalari
    app.add_handler(MessageHandler(
        filters.Regex("^(🇺🇿 O‘zbek|🇷🇺 Русский)$"),
        set_language
    ))

    # Menyu (katalog)
    app.add_handler(MessageHandler(filters.Regex("^📂 Menyu \\(katalog\\)$"), show_categories))
    app.add_handler(MessageHandler(filters.Regex("^📂 Меню \\(каталог\\)$"), show_categories))

    # Savatni ko‘rish / Корзина
    app.add_handler(MessageHandler(filters.Regex("^🧺 Savatni ko‘rish$"), show_cart))
    app.add_handler(MessageHandler(filters.Regex("^🧺 Корзина$"), show_cart))

    # Bekor qilish tugmalari
    app.add_handler(MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel))
    app.add_handler(MessageHandler(filters.Regex("^❌ Отмена$"), cancel))

    # Callbacklar
    app.add_handler(CallbackQueryHandler(show_products, pattern="^cat"))
    app.add_handler(CallbackQueryHandler(update_cart, pattern="^qty"))

    # Conversation handler (buyurtma jarayoni)
    app.add_handler(conv_handler)

    # Har qanday boshqa matn -> til / menyu
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, any_text))

    print("🤖 Bot ishga tushdi...")
    app.run_polling()


if __name__ == "__main__":
    main()
