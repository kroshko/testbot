!pip install python-telegram-bot==20.3 nest_asyncio

import asyncio
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

# Настраиваем логирование чтобы видеть что в момент будет происходить с ботом
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__) # содержит имя текущего модуля, можно бахнуть и print, но лучше так, гет возвращает уже сущ=ий объект

# Константы для состояний бота, range(2) так как передаем только вес и дату
GET_WEIGHT, GET_START_DATE = range(2)

# Токен бота из телеги
TOKEN = "7082988240:AAEO9nitwQ1ejFXVb5SXMHgIgwpG-EWV0q4"

# Словарь для хранения данных пользователей
user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int: #задаем ожидаемый тип данных (интовый)
    """Начало работы с ботом, показывает главное меню""" #описание ф-ий лучше писать через тройные, тк они пойдут в отчетность, а комменты пропускаются
    # Создаем кнопки для меню в тг
    menu_buttons = [
        ["Получить расчет"],
        ["Скачать расписание"],
        ["Вернуться в начало"]
    ]

    # Отправляем приветственное смс с кнопками
    #await поялвяется из асинхронного кода, т е учитываем то, что ждем ответ пользователя
    await update.message.reply_text(
        "Привет! Я помогу рассчитать дозировку витаминов.\n"
        "Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(
            menu_buttons,
            resize_keyboard=True,  # делаем кнопки компактными
            input_field_placeholder="Выберите действие"
        )
    )
    return GET_WEIGHT #вернется вес

async def handle_download(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отправляет файл с расписанием если он есть"""
    user_id = update.effective_user.id
    filename = f"vitamin_schedule_{user_id}.txt"

    try: # исп-ем try, так как сразу пытаемся отправить файл и задать условия дальше, если пол=ся и нет
        # Пытаемся отправить файл
        await update.message.reply_document(
            document=open(filename, "rb"),
            caption="Ваше расписание приема витаминов",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END #автоматически закончит процесс "беседы"
    except FileNotFoundError:
        # Если файла нет - сообщаем об этом
        await update.message.reply_text(
            "Сначала нужно получить расчет дозировк0и:)!",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает нажатия кнопок в меню"""
    user_choice = update.message.text

    if user_choice == "Вернуться в начало":
        return await start(update, context)
    elif user_choice == "Скачать расписание":
        return await handle_download(update, context)
    elif user_choice == "Получить расчет":
        await update.message.reply_text(
            "Введите ваш вес в килограммах:",
            reply_markup=ReplyKeyboardRemove()
        )
        return GET_WEIGHT
    else:
        # Если это не кнопка - продолжаем текущий диалог
        return await start(update, context)

async def get_weight(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получаем вес пользователя и рассчитываем минимальную дозу"""
    user_input = update.message.text

    # Обрабатываем кнопки меню
    if user_input == "Скачать расписание":
        return await handle_download(update, context)
    elif user_input == "Получить расчет":
        await update.message.reply_text("Введите ваш вес в кг:")
        return GET_WEIGHT
    elif user_input == "Вернуться в начало":
        return await start(update, context)

    # Пытаемся обработать введенный вес
    try:
        weight = float(user_input) #в целом как-будто float, надо проверитьь!!!
        if weight <= 0:
            raise ValueError("Вес должен быть больше нуля")

        # Сохраняем вес пользователя
        user_data['weight'] = weight

        # Определяем минимальную дозу по весу
        if weight < 60:
            min_dose = 0.1
        elif 60 <= weight <= 80:
            min_dose = 0.2
        else:
            min_dose = 0.4

        user_data['min_dose'] = min_dose

        # Просим дату начала курса
        await update.message.reply_text(
            f"Ваш вес: {weight} кг.\n" # Скачем по строкам 
            f"Начальная доза: {min_dose} мл.\n"
            "Введите дату начала курса (ДД.ММ.ГГГГ):",
            reply_markup=ReplyKeyboardRemove()
        )
        return GET_START_DATE # Возвращаем дату начала
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите число (например: 65.5)")
        return GET_WEIGHT

async def get_start_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получаем дату начала курса и создаем расписание"""
    try:
        # Пытаемся понять введенную дату
        date_str = update.message.text
        start_date = datetime.strptime(date_str, "%d.%m.%Y").date()
        today = datetime.now().date()

        # Проверяем что дата не в будущем
        if start_date > today:
            await update.message.reply_text("Дата не может быть в будущем! Введите снова:")
            return GET_START_DATE

        # Сохраняем дату и получаем вес пользователя
        user_data['start_date'] = start_date
        weight = user_data['weight']
        min_dose = user_data['min_dose']

        # Определяем параметры курса
        if weight < 60:
            max_dose = 4.0
            step = 0.1
        elif 60 <= weight <= 80:
            max_dose = 7.0
            step = 0.2
        else:
            max_dose = 8.0
            step = 0.4

        # Рассчитываем длительность курса
        days_to_max = int((max_dose - min_dose) / step)
        total_days = days_to_max * 2  # столько же дней нужно на снижение дозы

        # Проверяем закончился ли курс, чтобы можно было отследить длительность и ошибку при неверном вводе даты(ранней)
        end_date = start_date + timedelta(days=total_days)
        if today > end_date:
            await update.message.reply_text(
                f"Курс закончился {end_date.strftime('%d.%m.%Y')}. "
                f"Новая начальная доза: {min_dose} мл"
            )
            return ConversationHandler.END

        # Создаем расписание
        schedule = []
        current_date = start_date
        current_dose = min_dose

        # Фаза увеличения дозы
        for _ in range(days_to_max + 1):
            schedule.append((current_date, round(current_dose, 2))) # Решить, а нужно ли вообще округление!
            current_date += timedelta(days=1) # Надо делать такой скачок на день
            current_dose += step # Величина на которую увеличиваем, наш "шаг" 

        # Надо скорректировать максимальную дозу. Считаем с конца (отрицательные), -1 это последний эл-т, а вот [-1][0], это первый эл-т массива (дата) из Последней! записи
        schedule[-1] = (schedule[-1][0], max_dose) 

        # Фаза уменьшения дозы
        for _ in range(days_to_max):
            current_dose -= step
            schedule.append((current_date, round(current_dose, 2)))
            current_date += timedelta(days=1)
