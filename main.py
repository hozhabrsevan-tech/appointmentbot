
from datetime import datetime
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes
)

from config import BOT_TOKEN, ADMIN_ID
import database as db


def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 رزرو نوبت", callback_data="services")],
        [InlineKeyboardButton("📋 نوبت‌های من", callback_data="my_appointments")],
        [InlineKeyboardButton("ℹ️ راهنما", callback_data="help")]
    ])


def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 مشاهده نوبت‌ها", callback_data="admin_appointments")],
        [InlineKeyboardButton("🔙 منوی کاربر", callback_data="home")]
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(user.id, user.full_name)

    await update.message.reply_text(
        f"سلام {user.first_name} 🌷\nبه ربات نوبت‌دهی خوش اومدی.",
        reply_markup=main_keyboard()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "برای رزرو نوبت، دکمه رزرو نوبت رو بزن.\n"
        "برای دیدن نوبت‌های ثبت‌شده‌ات، نوبت‌های من رو انتخاب کن."
    )


async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ دسترسی ندارید.")
        return

    await update.message.reply_text(
        "🔐 پنل مدیریت\n\n"
        "دستورهای مدیر:\n"
        "/addservice نام|توضیحات|مدت به دقیقه|قیمت\n"
        "/addslot شناسه خدمت|تاریخ|شروع|پایان\n"
        "/manual شناسه خدمت|شناسه زمان|نام مشتری|شماره تلفن\n"
        "/holiday تاریخ|توضیحات\n"
        "/allappointments مشاهده همه نوبت‌ها",
        reply_markup=admin_keyboard()
    )


async def addservice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    try:
        data = " ".join(context.args).split("|")
        if len(data) != 4:
            raise ValueError

        name, description, duration, price = [item.strip() for item in data]
        duration = int(duration)
        price = int(price)

        if not name or duration <= 0 or price < 0:
            raise ValueError

        db.add_service(name, description, duration, price)
        await update.message.reply_text("✅ خدمت با موفقیت اضافه شد.")

    except ValueError:
        await update.message.reply_text(
            "فرمت دستور درست نیست.\n"
            "نمونه:\n"
            "/addservice ویزیت|معاینه عمومی|30|500000"
        )


async def addslot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    try:
        data = " ".join(context.args).split("|")
        if len(data) != 4:
            raise ValueError

        service_id = int(data[0].strip())
        slot_date = data[1].strip()
        start_time = data[2].strip()
        end_time = data[3].strip()

        day = datetime.strptime(slot_date, "%Y-%m-%d").date()
        start = datetime.strptime(start_time, "%H:%M")
        end = datetime.strptime(end_time, "%H:%M")

        if day < datetime.now().date() or end <= start:
            raise ValueError

        if not any(s["id"] == service_id for s in db.get_services()):
            await update.message.reply_text("❌ شناسه خدمت معتبر یا فعال نیست.")
            return

        db.add_time_slot(service_id, slot_date, start_time, end_time)
        await update.message.reply_text("✅ زمان خالی اضافه شد.")

    except ValueError:
        await update.message.reply_text(
            "فرمت دستور درست نیست یا تاریخ/ساعت نامعتبر است.\n"
            "نمونه:\n"
            "/addslot 1|2026-10-10|10:00|10:30"
        )
    except Exception:
        await update.message.reply_text(
            "❌ زمان اضافه نشد. ممکنه این زمان قبلاً ثبت شده باشه."
        )







async def allappointments_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    if update.effective_user.id != ADMIN_ID:
        return

    appointments = db.get_all_appointments()

    if not appointments:
        await update.message.reply_text("هنوز نوبتی ثبت نشده.")
        return

    for appointment in appointments:
        text = (
            f"🔹 نوبت شماره {appointment['id']}\n"
            f"👤 مشتری: {appointment['customer_name']}\n"
            f"📞 تلفن: {appointment['customer_phone'] or 'ثبت نشده'}\n"
            f"🩺 خدمت: {appointment['service_name']}\n"
            f"📅 تاریخ: {appointment['slot_date']}\n"
            f"🕒 ساعت: {appointment['start_time']} تا "
            f"{appointment['end_time']}\n"
            f"وضعیت: {appointment['status']}"
        )
        await update.message.reply_text(text)


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    user = update.effective_user

    if data == "home":
        await query.edit_message_text(
            "🏠 منوی اصلی",
            reply_markup=main_keyboard()
        )

    elif data == "help":
        await query.edit_message_text(
            "برای رزرو، خدمت و زمان دلخواهت رو انتخاب کن.\n"
            "از بخش نوبت‌های من هم می‌تونی نوبت‌هات رو ببینی یا لغو کنی.",
            reply_markup=main_keyboard()
        )

    elif data == "services":
        services = db.get_services()

        if not services:
            await query.edit_message_text(
                "فعلاً خدمتی برای رزرو وجود نداره.",
                reply_markup=main_keyboard()
            )
            return

        keyboard = [
            [InlineKeyboardButton(
                f"{service['name']} - {service['price']} تومان",
                callback_data=f"service:{service['id']}"
            )]
            for service in services
        ]
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="home")])

        await query.edit_message_text(
            "لطفاً خدمت موردنظرت رو انتخاب کن:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("service:"):
        service_id = int(data.split(":")[1])
        dates = db.get_available_dates(service_id)

        if not dates:
            await query.edit_message_text(
                "برای این خدمت فعلاً زمان خالی وجود نداره.",
                reply_markup=main_keyboard()
            )
            return

        keyboard = [
            [InlineKeyboardButton(
                row["slot_date"],
                callback_data=f"date:{service_id}:{row['slot_date']}"
            )]
            for row in dates
        ]
        keyboard.append([InlineKeyboardButton("🔙 خدمات", callback_data="services")])

        await query.edit_message_text(
            "📅 تاریخ موردنظرت رو انتخاب کن:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("date:"):
        _, service_id, slot_date = data.split(":", 2)
        service_id = int(service_id)
        slots = db.get_available_slots(service_id, slot_date)

        keyboard = [
            [InlineKeyboardButton(
                f"{slot['start_time']} تا {slot['end_time']}",
                callback_data=f"book:{service_id}:{slot['id']}"
            )]
            for slot in slots
        ]
        keyboard.append([
            InlineKeyboardButton(
                "🔙 تاریخ‌ها",
                callback_data=f"service:{service_id}"
            )
        ])

        await query.edit_message_text(
            "🕒 یکی از زمان‌های خالی رو انتخاب کن:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("book:"):
        _, service_id, slot_id = data.split(":")
        service_id = int(service_id)
        slot_id = int(slot_id)

        db.add_user(user.id, user.full_name)
        success = db.book_appointment(
            user.id, service_id, slot_id, user.full_name
        )

        if success:
            await query.edit_message_text(
                "✅ نوبتت با موفقیت ثبت شد.",
                reply_markup=main_keyboard()
            )
        else:
            await query.edit_message_text(
                "❌ متأسفانه این زمان دیگه در دسترس نیست. "
                "لطفاً زمان دیگه‌ای انتخاب کن.",
                reply_markup=main_keyboard()
            )

    elif data == "my_appointments":
        appointments = db.get_user_appointments(user.id)

        if not appointments:
            await query.edit_message_text(
                "شما نوبت تأییدشده‌ای نداری.",
                reply_markup=main_keyboard()
            )
            return

        for appointment in appointments:
            text = (
                f"📋 نوبت شماره {appointment['id']}\n"
                f"🩺 خدمت: {appointment['service_name']}\n"
                f"📅 تاریخ: {appointment['slot_date']}\n"
                f"🕒 ساعت: {appointment['start_time']} تا "
                f"{appointment['end_time']}"
            )
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "❌ لغو نوبت",
                    callback_data=f"cancel:{appointment['id']}"
                )
            ]])
            await query.message.reply_text(text, reply_markup=keyboard)

        await query.message.reply_text(
            "برای برگشت به منوی اصلی:",
            reply_markup=main_keyboard()
        )

    elif data.startswith("cancel:"):
        appointment_id = int(data.split(":")[1])
        success = db.cancel_appointment(appointment_id, user.id)

        if success:
            await query.edit_message_text("✅ نوبتت لغو شد.")
        else:
            await query.edit_message_text(
                "❌ نوبت پیدا نشد یا قبلاً لغو شده."
            )

    elif data == "admin_appointments":
        if user.id != ADMIN_ID:
            await query.edit_message_text("⛔ دسترسی ندارید.")
            return

        appointments = db.get_all_appointments()
        if not appointments:
            await query.edit_message_text("هنوز نوبتی ثبت نشده.")
            return

        await query.edit_message_text(
            f"تعداد نوبت‌ها: {len(appointments)}\n"
            "برای مشاهده جزئیات از دستور /allappointments استفاده کن."
        )


def main():
    if not BOT_TOKEN or ADMIN_ID == 0:
        raise ValueError("BOT_TOKEN و ADMIN_ID را در فایل .env تنظیم کن.")

    db.create_tables()
    db.add_admin(ADMIN_ID)

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("addservice", addservice_command))
    app.add_handler(CommandHandler("addslot", addslot_command))

    app.add_handler(CommandHandler("allappointments", allappointments_command))
    app.add_handler(CallbackQueryHandler(buttons))

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
