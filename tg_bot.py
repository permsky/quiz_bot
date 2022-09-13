import json
import logging
import os
from enum import Enum
from functools import partial
from random import choice
from textwrap import dedent, fill

import redis
import telegram
from dotenv import load_dotenv
from telegram.ext import (
    ConversationHandler,
    CommandHandler,
    Filters,
    MessageHandler,
    Updater
)


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class State(Enum):
    QUESTION = 1
    ANSWER = 2
    GIVE_UP = 3


def start(bot: telegram.bot.Bot, update: telegram.update.Update) -> State:
    """Send a message when the command /start is issued."""
    custom_keyboard = [['Новый вопрос', 'Сдаться'], ['Мой счет']]
    reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
    bot.send_message(
        chat_id=update.message.chat_id,
        text='Привет! Я бот для викторин!',
        reply_markup=reply_markup
    )
    return State.QUESTION


def help(bot: telegram.bot.Bot, update: telegram.update.Update) -> None:
    """Send a message when the command /help is issued."""
    update.message.reply_text('Введите команду /start для начала викторины.')


def handle_new_question_request(
    bot: telegram.bot.Bot,
    update: telegram.update.Update,
    questions: dict,
    db: redis.Redis
) -> State:
    """Send random question to user."""
    question, answer = choice(list(questions.items()))
    question = fill(question, width=55)
    answer = fill(answer, width=55)
    db.set(f'{update.message.chat_id}-question', question)
    db.set(f'{update.message.chat_id}-answer', answer)
    update.message.reply_text(f'Вопрос:\n{question}')
    return State.ANSWER


def handle_solution_attempt(
    bot: telegram.bot.Bot,
    update: telegram.update.Update,
    db: redis.Redis
) -> State:
    """Check user's answer."""
    chat_id = update.message.chat_id
    answer_from_db = db.get(f'{chat_id}-answer')
    answer_from_db_chunk = answer_from_db.split('.')[0]
    answer = answer_from_db_chunk.split('(')[0].strip().lower()
    if update.message.text.strip().lower() == answer:
        reply_text = '''\
        Правильно! Поздравляю! Для следующего вопроса нажми
        «Новый вопрос»
        '''
        custom_keyboard = [['Новый вопрос'], ['Мой счет']]
        reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
        bot.send_message(
            chat_id=chat_id,
            text=dedent(reply_text),
            reply_markup=reply_markup
        )
        return State.QUESTION
    else:
        reply_text = 'Неправильно… Попробуешь ещё раз?'
        custom_keyboard = [['Сдаться'], ['Мой счет']]
        reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
        bot.send_message(
            chat_id=chat_id,
            text=reply_text,
            reply_markup=reply_markup
        )
        return State.ANSWER


def handle_give_up(
    bot: telegram.bot.Bot,
    update: telegram.update.Update,
    questions: dict,
    db: redis.Redis
) -> State:
    """Process 'Сдаться' button click."""
    chat_id = update.message.chat_id
    reply_text = db.get(f'{chat_id}-answer')
    update.message.reply_text(f'Правильный ответ:\n{reply_text}')
    return handle_new_question_request(
        bot=bot,
        update=update,
        questions=questions,
        db=db
    )


def main() -> None:
    """Start the Telegram-bot."""
    load_dotenv()
    tg_token = os.getenv("TG_BOT_TOKEN")
    db_host = os.getenv("DB_HOST", default='localhost')
    db_port = os.getenv("DB_PORT", default=6379)
    db_password = os.getenv("DB_PASSWORD", default=None)

    with open('question-answer.json', 'r', encoding='utf-8') as json_file:
        questions = json.load(json_file)

    redis_db = redis.Redis(
        host=db_host,
        port=db_port,
        password=db_password,
        decode_responses=True
    )

    updater = Updater(tg_token)
    dp = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("help", help)
        ],
        states={
            State.QUESTION: [
                MessageHandler(
                    Filters.regex('^Новый вопрос$'),
                    partial(
                        handle_new_question_request,
                        questions=questions,
                        db=redis_db
                    )
                )
            ],
            State.ANSWER: [
                MessageHandler(
                    Filters.regex('^Сдаться$'),
                    partial(handle_give_up, questions=questions, db=redis_db)
                ),
                MessageHandler(
                    Filters.text, partial(
                        handle_solution_attempt,
                        db=redis_db
                    )
                ),
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
            CommandHandler("help", help)
        ]
    )

    dp.add_handler(conv_handler)

    updater.start_polling()

    updater.idle()


if __name__ == '__main__':
    main()
