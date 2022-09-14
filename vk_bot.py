import json
import logging
import os
from random import choice
from textwrap import dedent, fill

import redis
import vk_api as vk
from dotenv import load_dotenv
from vk_api.longpoll import VkLongPoll, VkEventType, Event
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.utils import get_random_id
from vk_api.vk_api import VkApiMethod


logger = logging.getLogger(__name__)


def start(event: Event, vk_api: VkApiMethod, keyboard: VkKeyboard) -> None:
    '''Send a message when the command /start is issued.'''
    vk_api.messages.send(
        user_id=event.user_id,
        message='Привет! Я бот для викторин!',
        random_id=get_random_id(),
        keyboard=keyboard.get_keyboard()
    )


def handle_new_question_request(
    event: Event,
    vk_api: VkApiMethod,
    questions: dict,
    db: redis.Redis,
    keyboard: VkKeyboard
) -> None:
    '''Send random question to user.'''
    user_id = event.user_id
    question, answer = choice(list(questions.items()))
    question = fill(question, width=55)
    answer = fill(answer, width=55)
    db.set(f'vk-{user_id}-question', question)
    db.set(f'vk-{user_id}-answer', answer)
    vk_api.messages.send(
        user_id=user_id,
        message=f'Вопрос:\n{question}',
        random_id=get_random_id(),
        keyboard=keyboard.get_keyboard()
    )


def handle_solution_attempt(
    event: Event,
    vk_api: VkApiMethod,
    db: redis.Redis,
    keyboard: VkKeyboard
) -> None:
    '''Check user's answer.'''
    user_id = event.user_id
    answer_from_db = db.get(f'vk-{user_id}-answer')
    answer_from_db_chunk = answer_from_db.split('.')[0]
    answer = answer_from_db_chunk.split('(')[0].strip().lower()
    if event.text.strip().lower() == answer:
        reply_text = '''\
        Правильно! Поздравляю! Для следующего вопроса нажми
        «Новый вопрос»
        '''
        vk_api.messages.send(
            user_id=user_id,
            message=dedent(reply_text),
            random_id=get_random_id(),
            keyboard=keyboard.get_keyboard()
        )
    else:
        reply_text = 'Неправильно… Попробуешь ещё раз?'
        vk_api.messages.send(
            user_id=user_id,
            message=reply_text,
            random_id=get_random_id(),
            keyboard=keyboard.get_keyboard()
        )


def handle_give_up(
    event: Event,
    vk_api: VkApiMethod,
    questions: dict,
    db: redis.Redis,
    keyboard: VkKeyboard
) -> None:
    '''Process 'Сдаться' button click.'''
    user_id = event.user_id
    reply_text = db.get(f'vk-{user_id}-answer')
    vk_api.messages.send(
            user_id=user_id,
            message=f'Правильный ответ:\n{reply_text}',
            random_id=get_random_id(),
            keyboard=keyboard.get_keyboard()
        )
    return handle_new_question_request(
        event=event,
        vk_api=vk_api,
        questions=questions,
        db=db,
        keyboard=keyboard
    )


def main() -> None:
    '''Start VK-bot.'''
    load_dotenv()
    vk_session = vk.VkApi(token=os.getenv('VK_GROUP_TOKEN'))
    db_host = os.getenv('DB_HOST', default='localhost')
    db_port = os.getenv('DB_PORT', default=6379)
    db_password = os.getenv('DB_PASSWORD', default=None)

    with open('question-answer.json', 'r', encoding='utf-8') as json_file:
        questions = json.load(json_file)

    redis_db = redis.Redis(
        host=db_host,
        port=db_port,
        password=db_password,
        decode_responses=True
    )

    longpoll = VkLongPoll(vk_session)
    vk_api = vk_session.get_api()
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button('Новый вопрос', color=VkKeyboardColor.PRIMARY)
    keyboard.add_button('Сдаться', color=VkKeyboardColor.NEGATIVE)
    keyboard.add_line()
    keyboard.add_button('Мой счет', color=VkKeyboardColor.SECONDARY)

    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            if event.text == 'Новый вопрос':
                handle_new_question_request(
                    event=event,
                    vk_api=vk_api,
                    questions=questions,
                    db=redis_db,
                    keyboard=keyboard
                )
            elif event.text == 'Сдаться':
                handle_give_up(
                    event=event,
                    vk_api=vk_api,
                    questions=questions,
                    db=redis_db,
                    keyboard=keyboard
                )
            elif event.text == 'Привет':
                start(
                    event=event,
                    vk_api=vk_api,
                    keyboard=keyboard
                )
            else:
                handle_solution_attempt(
                    event=event,
                    vk_api=vk_api,
                    db=redis_db,
                    keyboard=keyboard
                )


if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    
    main()
