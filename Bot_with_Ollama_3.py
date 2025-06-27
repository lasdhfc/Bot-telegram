import re
import requests
from telegram import Update
from telegram.ext import Application, MessageHandler, filters
from ollama import chat
import threading
from telegram.error import TimedOut

#Модель ИИ
model = 'mistral:7b-instruct'

# Токен Telegram-бота
TELEGRAM_TOKEN = ''

# Регулярные выражения
# MOBILE_PHONE_REGEX = r'(\+7|8)(?:[\s\-()]?\d){10}'
# INTERNAL_PHONE_REGEX = r'\b\d{4}\b'
# OFFICE_REGEX = r'\b\d{3}\w{,3}\b'

# Обновленные регулярные выражения
MOBILE_PHONE_REGEX = r'(?:(?:\+7|8)[\s\-()]?\d{3}[\s\-()]?\d{3}[\s\-()]?\d{2}[\s\-()]?\d{2}|\b\d{10}\b)'
INTERNAL_PHONE_REGEX = r'(?i)(?:(?:тел\.?|телефон|вн\.?|доб\.?)[:\s]*)?(\b\d{4}\b)'
OFFICE_REGEX = r'(?<!\d)(?:каб(?:инет)?[а-я]*[\s:]*)?(\d{3})(?!\d)'


# Загрузка шаблонов промтов
try:
    with open('prompt_name.txt', 'r', encoding='utf-8') as f:
        PROMPT_NAME = f.read()
    with open('prompt_request.txt', 'r', encoding='utf-8') as f:
        PROMPT_REQUEST = f.read()
    with open('prompt_description.txt', 'r', encoding='utf-8') as f:
    	PROMPT_DESCRIPTION = f.read()
    with open('prompt_emotion.txt', 'r', encoding='utf-8') as f:
        PROMPT_EMOTION = f.read()
except FileNotFoundError:
    logging.error("Prompt files not found. Please create 'prompt_name.txt', 'prompt_request.txt', 'prompt_description.txt' and 'prompt_emotion.txt'.")
    exit(1)

def analyze_with_ollama(prompt, message):
    try:
        response = chat(model=model, messages=[{'role': 'user', 'content': prompt.format(message=message)}])
        return response['message']['content'].strip()
    except Exception as e:
        logging.error(f"Ошибка при работе с Ollama: {e}")
        return None
    
async def handle_message(update: Update, context):
    message = update.message.text or update.message.caption or ''
    if not message:
    	return
    chat_id = update.message.chat_id
    message_id = update.message.message_id

    # Извлечение номера телефона
    phone_match = re.search(MOBILE_PHONE_REGEX, message) or re.search(INTERNAL_PHONE_REGEX, message)
    phone_number = phone_match.group(0) if phone_match else None

    # Извлечение номера кабинета
    office_match = re.search(OFFICE_REGEX, message)
    office_number = office_match.group(0)[:3] if office_match else None
    
    # Удаление номеров из сообщения
    patterns = [MOBILE_PHONE_REGEX, INTERNAL_PHONE_REGEX, OFFICE_REGEX]
    cleaned_message = message
    for pattern in patterns:
        cleaned_message = re.sub(pattern, '', cleaned_message)
    cleaned_message = re.sub(r'\s+', ' ', cleaned_message).strip()
    print(cleaned_message)

    # Хранилище результатов
    results = {}

    # Функции для параллельных запросов
    def get_name():
        results['name'] = analyze_with_ollama(PROMPT_NAME, cleaned_message)

    def get_request():
        results['is_request'] = analyze_with_ollama(PROMPT_REQUEST, cleaned_message)

    def get_emotion():
        results['emotional_tone'] = analyze_with_ollama(PROMPT_EMOTION, cleaned_message)

    def get_description():
    	results['problem_description'] = analyze_with_ollama(PROMPT_DESCRIPTION, cleaned_message)
    
    # Создание и запуск потоков
    threads = [
        threading.Thread(target=get_name, name='name'),
        threading.Thread(target=get_request, name='request'),
        threading.Thread(target=get_description, name='description'),
        threading.Thread(target=get_emotion, name='emotion')
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    # Сохранение данных
    data = {
#         'message': message,
        'phone_number': phone_number,
        'office_number': office_number,
        'name': results.get('name'),
        'is_request': results.get('is_request'),
        'problem_description': results.get('problem_description'),
        'emotional_tone': results.get('emotional_tone')
    }

    # Вывод данных для отладки
    print(data)

    # Обратная связь
    if results.get('is_request', '').lower() == 'да':
        if phone_number and office_number and results.get('name') != "Нет" and results.get('problem_description') != "Нет":
        	try:
        		await update.message.reply_text("Заявка принята в работу")
        	except TimedOut:
        		print("Timeout при отправке сообщения")
#             await context.bot.send_message(chat_id=chat_id, text="Заявка принята в работу", reply_to_message_id=message_id)
        else:
        	try:
        		await update.message.reply_text("Нарушение в оформлении заявки")
        	except TimedOut:
        		print("Timeout при отправке сообщения")
#             await context.bot.send_message(chat_id=chat_id, text="Нарушение в оформлении заявки", reply_to_message_id=message_id)

def main():
    requests.post(
    	"http://localhost:11434/api/generate",
    	json={"model": model, "prompt": "Hello"}
    )
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(MessageHandler(filters.ALL, handle_message))
    application.run_polling()

if __name__ == '__main__':
    main()
