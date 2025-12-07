import telebot
from telebot import types
import sqlite3
from datetime import datetime, timedelta
import threading
import time
import os

# Бот для управления учебными заданиями и расписанием
# Функции: добавление/удаление/редактирование заданий, просмотр списка, расписание, статистика, уведомления
# Ссылка на бота @StepochkinDzBot

TOKEN = '8504597965:AAFdYv5kLCMAOwBSksLXeB-NPEGU9scl6ME'
bot = telebot.TeleBot(TOKEN)

# Инициализация БД
def init_db():
    conn = sqlite3.connect('study_bot.db', check_same_thread=False)
    cur = conn.cursor()

    cur.execute('''CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        subject TEXT,
        task TEXT,
        deadline TEXT,
        deadline_datetime TEXT,
        completed INTEGER DEFAULT 0,
        notified INTEGER DEFAULT 0,
        created_at TEXT
    )''')

    cur.execute('''CREATE TABLE IF NOT EXISTS schedule (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        day_of_week TEXT,
        time TEXT,
        subject TEXT,
        room TEXT
    )''')

    conn.commit()
    return conn

conn = init_db()

# Главное меню
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('📝 Задания', '📅 Расписание')
    markup.row('📊 Статистика', '❓ Помощь')
    return markup

# Функция уведомлений
def check_deadlines():
    while True:
        try:
            cur = conn.cursor()
            now = datetime.now()
            one_hour_later = now + timedelta(hours=1)

            cur.execute('''SELECT id, user_id, subject, task, deadline_datetime
                          FROM tasks
                          WHERE completed = 0 AND notified = 0 AND deadline_datetime IS NOT NULL''')
            tasks = cur.fetchall()

            for task in tasks:
                task_time = datetime.strptime(task[4], '%Y-%m-%d %H:%M')

                if now <= task_time <= one_hour_later:
                    try:
                        bot.send_message(task[1],
                            f"⏰ Напоминание!\n\n"
                            f"📚 {task[2]}\n"
                            f"📝 {task[3]}\n"
                            f"⏳ Дедлайн через час!")

                        cur.execute('UPDATE tasks SET notified = 1 WHERE id = ?', (task[0],))
                        conn.commit()
                    except:
                        pass

            time.sleep(300)
        except:
            time.sleep(300)

# Запуск потока для уведомлений
notification_thread = threading.Thread(target=check_deadlines, daemon=True)
notification_thread.start()

# Команды бота
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id,
        f"Привет, {message.from_user.first_name}! 👋\n\n"
        "Я помогу тебе организовать учебу:\n"
        "• Отслеживать задания и дедлайны\n"
        "• Хранить расписание занятий\n"
        "• Смотреть статистику выполнения\n\n"
        "Выбери действие:",
        reply_markup=main_menu())

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.send_message(message.chat.id,
        "📖 Доступные команды:\n\n"
        "📝 Задания - управление заданиями\n"
        "📅 Расписание - расписание занятий\n"
        "📊 Статистика - твой прогресс\n"
        "❓ Помощь - это сообщение",
        reply_markup=main_menu())

# Функция 1: Меню заданий
@bot.message_handler(func=lambda m: m.text == '📝 Задания')
def tasks_menu(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('➕ Добавить задание', callback_data='add_task'))
    markup.add(types.InlineKeyboardButton('📋 Все задания', callback_data='view_all_tasks'))
    markup.add(types.InlineKeyboardButton('📆 Сегодня', callback_data='view_today'))
    markup.add(types.InlineKeyboardButton('📅 На неделю', callback_data='view_week'))
    markup.add(types.InlineKeyboardButton('✏️ Редактировать задание', callback_data='edit_task'))
    markup.add(types.InlineKeyboardButton('✅ Отметить выполненное', callback_data='complete_task'))
    markup.add(types.InlineKeyboardButton('🗑 Удалить задание', callback_data='delete_task'))

    bot.send_message(message.chat.id, "Выбери действие:", reply_markup=markup)

# Функция 2: Добавление задания
@bot.callback_query_handler(func=lambda call: call.data == 'add_task')
def add_task_start(call):
    msg = bot.send_message(call.message.chat.id,
        "Введи задание в формате:\n"
        "Предмет | Задание | Дедлайн | Время\n\n"
        "Например:\n"
        "Математика | Решить задачи 1-10 | 15.12.2024 | 14:00\n\n"
        "Время необязательно (для уведомлений)")
    bot.register_next_step_handler(msg, save_task)

def save_task(message):
    try:
        parts = message.text.split('|')
        subject = parts[0].strip()
        task = parts[1].strip()
        deadline = parts[2].strip()

        deadline_datetime = None
        if len(parts) >= 4:
            time_str = parts[3].strip()
            deadline_datetime = f"{deadline.split('.')[2]}-{deadline.split('.')[1]}-{deadline.split('.')[0]} {time_str}"

        cur = conn.cursor()
        cur.execute('''INSERT INTO tasks (user_id, subject, task, deadline, deadline_datetime, created_at)
                      VALUES (?, ?, ?, ?, ?, ?)''',
                   (message.chat.id, subject, task, deadline, deadline_datetime, datetime.now().strftime('%Y-%m-%d %H:%M')))
        conn.commit()

        notification_info = "\n⏰ Уведомление за час до дедлайна включено!" if deadline_datetime else ""
        bot.send_message(message.chat.id, f"✅ Задание добавлено!{notification_info}", reply_markup=main_menu())
    except:
        bot.send_message(message.chat.id, "❌ Ошибка! Проверь формат ввода.", reply_markup=main_menu())

# Функция 3: Просмотр всех заданий
@bot.callback_query_handler(func=lambda call: call.data == 'view_all_tasks')
def view_all_tasks(call):
    cur = conn.cursor()
    cur.execute('SELECT id, subject, task, deadline, completed FROM tasks WHERE user_id = ?',
               (call.message.chat.id,))
    tasks = cur.fetchall()

    if not tasks:
        bot.send_message(call.message.chat.id, "У тебя пока нет заданий 📭")
        return

    response = "📋 Твои задания:\n\n"
    for task in tasks:
        status = "✅" if task[4] else "⏳"
        response += f"{status} [{task[0]}] {task[1]}\n📝 {task[2]}\n⏰ До: {task[3]}\n\n"

    bot.send_message(call.message.chat.id, response)

# Функция 4: Просмотр заданий на сегодня
@bot.callback_query_handler(func=lambda call: call.data == 'view_today')
def view_today_tasks(call):
    today = datetime.now().strftime('%d.%m.%Y')
    cur = conn.cursor()
    cur.execute('SELECT id, subject, task, deadline, completed FROM tasks WHERE user_id = ? AND deadline = ?',
               (call.message.chat.id, today))
    tasks = cur.fetchall()

    if not tasks:
        bot.send_message(call.message.chat.id, "На сегодня заданий нет! 🎉")
        return

    response = "📆 Задания на сегодня:\n\n"
    for task in tasks:
        status = "✅" if task[4] else "⏳"
        response += f"{status} [{task[0]}] {task[1]}\n📝 {task[2]}\n\n"

    bot.send_message(call.message.chat.id, response)

# Функция 5: Просмотр заданий на неделю
@bot.callback_query_handler(func=lambda call: call.data == 'view_week')
def view_week_tasks(call):
    cur = conn.cursor()
    cur.execute('SELECT id, subject, task, deadline, completed FROM tasks WHERE user_id = ? AND completed = 0',
               (call.message.chat.id,))
    tasks = cur.fetchall()

    if not tasks:
        bot.send_message(call.message.chat.id, "Заданий на неделю нет! 🎉")
        return

    week_end = (datetime.now() + timedelta(days=7)).strftime('%d.%m.%Y')
    response = f"📅 Задания до {week_end}:\n\n"

    for task in tasks:
        response += f"[{task[0]}] {task[1]}\n📝 {task[2]}\n⏰ {task[3]}\n\n"

    bot.send_message(call.message.chat.id, response)

# Функция 6: Редактирование задания
@bot.callback_query_handler(func=lambda call: call.data == 'edit_task')
def edit_task_start(call):
    cur = conn.cursor()
    cur.execute('SELECT id, subject, task FROM tasks WHERE user_id = ?',
               (call.message.chat.id,))
    tasks = cur.fetchall()

    if not tasks:
        bot.send_message(call.message.chat.id, "Нет заданий для редактирования!")
        return

    markup = types.InlineKeyboardMarkup()
    for task in tasks:
        markup.add(types.InlineKeyboardButton(
            f"[{task[0]}] {task[1]}: {task[2][:30]}...",
            callback_data=f'edit_{task[0]}'))

    bot.send_message(call.message.chat.id, "Выбери задание для редактирования:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_') and not call.data.startswith('edit_field_'))
def edit_task_choose_field(call):
    task_id = call.data.split('_')[1]

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('📚 Предмет', callback_data=f'edit_field_subject_{task_id}'))
    markup.add(types.InlineKeyboardButton('📝 Задание', callback_data=f'edit_field_task_{task_id}'))
    markup.add(types.InlineKeyboardButton('⏰ Дедлайн', callback_data=f'edit_field_deadline_{task_id}'))

    bot.send_message(call.message.chat.id, "Что хочешь изменить?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_field_'))
def edit_task_field(call):
    parts = call.data.split('_')
    field = parts[2]
    task_id = parts[3]

    field_names = {
        'subject': 'предмет',
        'task': 'задание',
        'deadline': 'дедлайн (формат: 15.12.2024 или 15.12.2024 | 14:00)'
    }

    msg = bot.send_message(call.message.chat.id, f"Введи новый {field_names[field]}:")
    bot.register_next_step_handler(msg, update_task_field, task_id, field)

def update_task_field(message, task_id, field):
    try:
        new_value = message.text.strip()
        cur = conn.cursor()

        if field == 'deadline':
            if '|' in new_value:
                parts = new_value.split('|')
                deadline = parts[0].strip()
                time_str = parts[1].strip()
                deadline_datetime = f"{deadline.split('.')[2]}-{deadline.split('.')[1]}-{deadline.split('.')[0]} {time_str}"
                cur.execute('UPDATE tasks SET deadline = ?, deadline_datetime = ?, notified = 0 WHERE id = ?',
                           (deadline, deadline_datetime, task_id))
            else:
                cur.execute('UPDATE tasks SET deadline = ?, deadline_datetime = NULL, notified = 0 WHERE id = ?',
                           (new_value, task_id))
        else:
            cur.execute(f'UPDATE tasks SET {field} = ? WHERE id = ?', (new_value, task_id))

        conn.commit()
        bot.send_message(message.chat.id, "✅ Задание обновлено!", reply_markup=main_menu())
    except Exception as e:
        bot.send_message(message.chat.id, "❌ Ошибка при обновлении!", reply_markup=main_menu())

# Функция 7: Отметить выполненное
@bot.callback_query_handler(func=lambda call: call.data == 'complete_task')
def complete_task_start(call):
    cur = conn.cursor()
    cur.execute('SELECT id, subject, task FROM tasks WHERE user_id = ? AND completed = 0',
               (call.message.chat.id,))
    tasks = cur.fetchall()

    if not tasks:
        bot.send_message(call.message.chat.id, "Нет активных заданий!")
        return

    markup = types.InlineKeyboardMarkup()
    for task in tasks:
        markup.add(types.InlineKeyboardButton(
            f"[{task[0]}] {task[1]}: {task[2][:30]}...",
            callback_data=f'mark_done_{task[0]}'))

    bot.send_message(call.message.chat.id, "Выбери выполненное задание:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('mark_done_'))
def mark_task_done(call):
    task_id = call.data.split('_')[2]
    cur = conn.cursor()
    cur.execute('UPDATE tasks SET completed = 1 WHERE id = ?', (task_id,))
    conn.commit()

    bot.answer_callback_query(call.id, "✅ Задание выполнено!")
    bot.send_message(call.message.chat.id, "Отлично! Задание отмечено как выполненное 🎯")

# Функция 8: Удаление задания
@bot.callback_query_handler(func=lambda call: call.data == 'delete_task')
def delete_task_start(call):
    cur = conn.cursor()
    cur.execute('SELECT id, subject, task FROM tasks WHERE user_id = ?',
               (call.message.chat.id,))
    tasks = cur.fetchall()

    if not tasks:
        bot.send_message(call.message.chat.id, "Нет заданий для удаления!")
        return

    markup = types.InlineKeyboardMarkup()
    for task in tasks:
        markup.add(types.InlineKeyboardButton(
            f"[{task[0]}] {task[1]}: {task[2][:30]}...",
            callback_data=f'del_{task[0]}'))

    bot.send_message(call.message.chat.id, "Выбери задание для удаления:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('del_'))
def delete_task(call):
    task_id = call.data.split('_')[1]
    cur = conn.cursor()
    cur.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
    conn.commit()

    bot.answer_callback_query(call.id, "🗑 Задание удалено")
    bot.send_message(call.message.chat.id, "Задание удалено из списка")

# Меню расписания
@bot.message_handler(func=lambda m: m.text == '📅 Расписание')
def schedule_menu(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('➕ Добавить занятие', callback_data='add_schedule'))
    markup.add(types.InlineKeyboardButton('👀 Посмотреть расписание', callback_data='view_schedule'))
    markup.add(types.InlineKeyboardButton('🗑 Удалить занятие', callback_data='delete_schedule'))

    bot.send_message(message.chat.id, "Расписание занятий:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == 'add_schedule')
def add_schedule_start(call):
    msg = bot.send_message(call.message.chat.id,
        "Введи занятие в формате:\n"
        "День | Время | Предмет | Аудитория\n\n"
        "Например:\n"
        "Понедельник | 09:00 | Математика | 301")
    bot.register_next_step_handler(msg, save_schedule)

def save_schedule(message):
    try:
        parts = message.text.split('|')
        day = parts[0].strip()
        time = parts[1].strip()
        subject = parts[2].strip()
        room = parts[3].strip()

        cur = conn.cursor()
        cur.execute('''INSERT INTO schedule (user_id, day_of_week, time, subject, room)
                      VALUES (?, ?, ?, ?, ?)''',
                   (message.chat.id, day, time, subject, room))
        conn.commit()

        bot.send_message(message.chat.id, "✅ Занятие добавлено!", reply_markup=main_menu())
    except:
        bot.send_message(message.chat.id, "❌ Ошибка! Проверь формат ввода.", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda call: call.data == 'view_schedule')
def view_schedule(call):
    cur = conn.cursor()
    cur.execute('SELECT day_of_week, time, subject, room FROM schedule WHERE user_id = ? ORDER BY day_of_week',
               (call.message.chat.id,))
    schedule = cur.fetchall()

    if not schedule:
        bot.send_message(call.message.chat.id, "Расписание пустое 📭")
        return

    response = "📅 Твое расписание:\n\n"
    current_day = ""
    for item in schedule:
        if item[0] != current_day:
            current_day = item[0]
            response += f"\n📌 {current_day}\n"
        response += f"   🕐 {item[1]} - {item[2]} (ауд. {item[3]})\n"

    bot.send_message(call.message.chat.id, response)

@bot.callback_query_handler(func=lambda call: call.data == 'delete_schedule')
def delete_schedule_start(call):
    cur = conn.cursor()
    cur.execute('SELECT id, day_of_week, time, subject FROM schedule WHERE user_id = ?',
               (call.message.chat.id,))
    schedule = cur.fetchall()

    if not schedule:
        bot.send_message(call.message.chat.id, "Нет занятий для удаления!")
        return

    markup = types.InlineKeyboardMarkup()
    for item in schedule:
        markup.add(types.InlineKeyboardButton(
            f"{item[1]} {item[2]} - {item[3]}",
            callback_data=f'delsch_{item[0]}'))

    bot.send_message(call.message.chat.id, "Выбери занятие для удаления:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('delsch_'))
def delete_schedule(call):
    schedule_id = call.data.split('_')[1]
    cur = conn.cursor()
    cur.execute('DELETE FROM schedule WHERE id = ?', (schedule_id,))
    conn.commit()

    bot.answer_callback_query(call.id, "🗑 Занятие удалено")
    bot.send_message(call.message.chat.id, "Занятие удалено из расписания")

# Статистика
@bot.message_handler(func=lambda m: m.text == '📊 Статистика')
def statistics(message):
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM tasks WHERE user_id = ?', (message.chat.id,))
    total = cur.fetchone()[0]

    cur.execute('SELECT COUNT(*) FROM tasks WHERE user_id = ? AND completed = 1', (message.chat.id,))
    completed = cur.fetchone()[0]

    cur.execute('SELECT COUNT(*) FROM tasks WHERE user_id = ? AND completed = 0', (message.chat.id,))
    active = cur.fetchone()[0]

    if total == 0:
        percentage = 0
    else:
        percentage = (completed / total) * 100

    response = f"📊 Твоя статистика:\n\n"
    response += f"📝 Всего заданий: {total}\n"
    response += f"✅ Выполнено: {completed}\n"
    response += f"⏳ Активных: {active}\n"
    response += f"📈 Прогресс: {percentage:.1f}%\n"

    bot.send_message(message.chat.id, response, reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == '❓ Помощь')
def help_menu(message):
    help_command(message)

if __name__ == '__main__':
    print("Бот запущен...")
    bot.infinity_polling()