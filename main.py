!pip install python-telegram-bot==20.3 nest_asyncio

import asyncio
import nest_asyncio
nest_asyncio.apply()

import logging
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы
GET_WEIGHT, GET_START_DATE = range(2)
TOKEN = "7082988240:AAEO9nitwQ1ejFXVb5SXMHgIgwpG-EWV0q4"
BOT_NAME = "VitaminBot"

# Глобальные переменные для хранения данных пользователя
user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начинает диалог и спрашивает вес пользователя."""
    reply_keyboard = [["Получить расчет"], ["Скачать расписание"]]

    await update.message.reply_text(
        "Привет! Я помогу рассчитать дозировку.\n"
        "Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, input_field_placeholder="Выберите действие"
        )
    )
    return GET_WEIGHT

async def handle_download(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает запрос на скачивание расписания."""
    user_id = update.effective_user.id
    filename = f"vitamin_schedule_{user_id}.txt"

    try:
        await update.message.reply_document(
            document=open(filename, "rb"),
            caption="Ваше расписание курса витамина",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    except FileNotFoundError:
        await update.message.reply_text(
            "Расписание не найдено. Пожалуйста, сначала получите расчет.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

async def get_weight(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод веса или выбор действия."""
    text = update.message.text

    # Если пользователь выбрал "Скачать расписание"
    if text == "Скачать расписание":
        return await handle_download(update, context)

    # Если пользователь выбрал "Получить расчет" или отправил вес
    if text == "Получить расчет":
        await update.message.reply_text(
            "Пожалуйста, введите ваш вес в кг:",
            reply_markup=ReplyKeyboardRemove()
        )
        return GET_WEIGHT

    # Обработка ввода веса
    try:
        weight = float(text)
        if weight <= 0:
            raise ValueError("Вес должен быть положительным числом")

        user_data['weight'] = weight

        # Автоматически определяем минимальную дозу по весу
        if weight < 60:
            min_dose = 0.1
        elif 60 <= weight <= 80:
            min_dose = 0.2
        else:
            min_dose = 0.4

        user_data['min_dose'] = min_dose

        await update.message.reply_text(
            f"Ваш вес: {weight} кг.\n"
            f"Минимальная дозировка для вашего веса составляет: {min_dose} мл.\n"
            "Теперь введите дату начала курса в формате ДД.ММ.ГГГГ:",
            reply_markup=ReplyKeyboardRemove()
        )
        return GET_START_DATE
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите корректное число для веса.")
        return GET_WEIGHT

async def get_start_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет дату начала курса и рассчитывает расписание."""
    try:
        date_str = update.message.text
        start_date = datetime.strptime(date_str, "%d.%m.%Y").date()
        today = datetime.now().date()

        if start_date > today:
            await update.message.reply_text("Дата начала курса не может быть в будущем. Пожалуйста, введите корректную дату.")
            return GET_START_DATE

        user_data['start_date'] = start_date
        weight = user_data['weight']
        min_dose = user_data['min_dose']

        # Определяем параметры курса в зависимости от веса
        if weight < 60:
            max_dose = 4.0
            step = 0.1
        elif 60 <= weight <= 80:
            max_dose = 7.0
            step = 0.2
        else:
            max_dose = 8.0
            step = 0.4

        # Рассчитываем количество дней для наращивания дозы
        days_to_max = int((max_dose - min_dose) / step)
        total_days = days_to_max * 2  # столько же дней на уменьшение

        # Проверяем, закончился ли курс
        end_date = start_date + timedelta(days=total_days)
        if today > end_date:
            await update.message.reply_text(
                f"Курс закончился {end_date.strftime('%d.%m.%Y')}. "
                f"Начните новый курс с дозы: {min_dose} мл",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END

        schedule = []
        current_date = start_date
        current_dose = min_dose

        # Фаза увеличения дозы
        for _ in range(days_to_max + 1):
            schedule.append((current_date, round(current_dose, 2)))
            current_date += timedelta(days=1)
            current_dose += step

        # Корректируем последнюю дозу до точного максимума
        current_dose = max_dose
        schedule[-1] = (schedule[-1][0], max_dose)

        # Фаза уменьшения дозы
        for _ in range(days_to_max):
            current_dose -= step
            schedule.append((current_date, round(current_dose, 2)))
            current_date += timedelta(days=1)

        user_data['schedule'] = schedule

        # Находим текущую дозу
        current_dose_info = None
        for date, dose in schedule:
            if date <= today:
                current_dose_info = (date, dose)
            else:
                break

        # Формируем сообщение с результатами
        if current_dose_info:
            message = (
                f"На {today.strftime('%d.%m.%Y')} ваша дозировка: {current_dose_info[1]} мл\n"
                f"Дата начала курса: {start_date.strftime('%d.%m.%Y')}\n"
                f"Минимальная доза: {min_dose} мл\n"
                f"Максимальная доза: {max_dose} мл\n"
                f"Шаг изменения: {step} мл\n"
                f"Общая продолжительность курса: {total_days} дней\n"
                f"Дата окончания курса: {end_date.strftime('%d.%m.%Y')}"
            )
        else:
            message = f"Курс начнется {start_date.strftime('%d.%m.%Y')}. Начните с дозы: {min_dose} мл"

        await update.message.reply_text(message)

        # Отправляем файл с расписанием сразу после расчета
        filename = f"vitamin_schedule_{update.effective_user.id}.txt"
        with open(filename, "w") as f:
            f.write("Дата\t\tДозировка (мл)\n")
            for date, dose in schedule:
                f.write(f"{date.strftime('%d.%m.%Y')}\t{dose}\n")

        await update.message.reply_document(
            document=open(filename, "rb"),
            caption="Полное расписание курса"
        )

        # Предлагаем возможность скачать расписание снова
        reply_keyboard = [["Скачать расписание"]]
        await update.message.reply_text(
            "Вы можете скачать расписание снова:",
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard, one_time_keyboard=True, input_field_placeholder="Скачать расписание"
            )
        )

        return ConversationHandler.END
    except ValueError as e:
        await update.message.reply_text("Пожалуйста, введите дату в формате ДД.ММ.ГГГГ.")
        return GET_START_DATE

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет диалог."""
    await update.message.reply_text(
        "Диалог отменен.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Логирует ошибки."""
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

def run_bot():
    """Запуск бота с обработкой event loop для Colab"""
    application = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            GET_WEIGHT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_weight)
            ],
            GET_START_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_start_date)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conv_handler)
    application.add_error_handler(error_handler)

    logger.info(f"Бот {BOT_NAME} запущен")
    print(f"Бот {BOT_NAME} работает! Напишите /start в Telegram")

    # Особый запуск для Colab
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        application.run_polling()
    finally:
        loop.close()

if __name__ == '__main__':
    run_bot()
