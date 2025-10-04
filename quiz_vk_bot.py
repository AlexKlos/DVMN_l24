from environs import env
import redis
import vk_api as vk
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id

from quiz_bot_shared_utils import get_qa_dict, cut_answer, normalize_answer


def send(vk_api, user_id, text, keyboard):
    vk_api.messages.send(
        user_id=user_id,
        message=text,
        keyboard=keyboard.get_keyboard(),
        random_id=get_random_id(),
    )


def make_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button('Новый вопрос', color=VkKeyboardColor.SECONDARY)
    keyboard.add_button('Сдаться', color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button('Мой счёт', color=VkKeyboardColor.SECONDARY)
    return keyboard



def echo(event, vk_api, keyboard):
    send(vk_api, event.user_id, event.text, keyboard)


def user_keys(user_id):
    base = f'user:{user_id}'
    return {
        'idx': f'{base}:idx',
        'q': f'{base}:current_question',
        'a': f'{base}:current_answer',
        'score': f'{base}:score',
        'state': f'{base}:state',
    }


def ask_new_question_vk(event, vk_api, rds, quiz_items, keyboard):
    keys = user_keys(event.user_id)
    if not quiz_items:
        send(vk_api, event.user_id, 'Нет вопросов', keyboard)
        rds.set(keys['state'], 'IDLE')
        return
    
    raw_idx = rds.get(keys['idx'])
    idx = int(raw_idx) if raw_idx is not None else 0
    if idx >= len(quiz_items):
        idx = 0
    question, full_answer = quiz_items[idx]
    short_answer = cut_answer(full_answer)
    rds.set(keys['q'], question)
    rds.set(keys['a'], short_answer)
    rds.set(keys['idx'], idx + 1)
    rds.set(keys['state'], 'ASKING')
    send(vk_api, event.user_id, question.strip(), keyboard)


def check_answer_vk(event, vk_api, rds, keyboard):
    keys = user_keys(event.user_id)
    expected = rds.get(keys['a']) or ''
    user_text = event.text or ''
    if normalize_answer(user_text) == normalize_answer(expected):
        rds.incr(keys['score'], 1)
        send(
            vk_api,
            event.user_id,
            'Правильно! Поздравляю! Для следующего вопроса нажми «Новый вопрос»',
            keyboard,
        )
        rds.delete(keys['q'])
        rds.delete(keys['a'])
        rds.set(keys['state'], 'IDLE')
    else:
        send(vk_api, event.user_id, 'Неправильно… Попробуешь ещё раз?', keyboard)
        rds.set(keys['state'], 'ASKING')


def give_up_vk(event, vk_api, rds, quiz_items, keyboard):
    keys = user_keys(event.user_id)
    correct = rds.get(keys['a'])
    if correct:
        send(vk_api, event.user_id, f'Правильный ответ: {correct}', keyboard)
    else:
        send(vk_api, event.user_id, 'Вопрос не был задан', keyboard)
    ask_new_question_vk(event, vk_api, rds, quiz_items, keyboard)


def show_score_vk(event, vk_api, rds, keyboard):
    keys = user_keys(event.user_id)
    raw = rds.get(keys['score'])
    score = int(raw) if raw is not None else 0
    send(vk_api, event.user_id, f'Твой счёт: {score}', keyboard)


def main():
    env.read_env()
    VK_TOKEN = env.str('VK_TOKEN')
    REDIS_HOST = env.str('REDIS_HOST')
    REDIS_PORT = env.int('REDIS_PORT')
    REDIS_DB = env.int('REDIS_DB', 0)
    REDIS_PASSWORD = env.str('REDIS_PASSWORD')
    QUIZ_FILE = env.str('QUIZ_FILE')
    ENCODING = env.str('ENCODING')

    quiz = get_qa_dict(QUIZ_FILE, ENCODING)
    quiz_items = list(quiz.items())

    rds = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        password=REDIS_PASSWORD,
        decode_responses=True,
    )

    vk_session = vk.VkApi(token=VK_TOKEN)
    vk_api = vk_session.get_api()

    keyboard = make_keyboard()
    longpoll = VkLongPoll(vk_session)
    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            text = (event.text or '').strip()
            keys = user_keys(event.user_id)
            state = rds.get(keys['state']) or 'IDLE'
    
            match text:
                case 'Новый вопрос':
                    ask_new_question_vk(event, vk_api, rds, quiz_items, keyboard)
                case 'Сдаться':
                    give_up_vk(event, vk_api, rds, quiz_items, keyboard)
                case 'Мой счёт':
                    show_score_vk(event, vk_api, rds, keyboard)
                case _:
                    if state == 'ASKING':
                        check_answer_vk(event, vk_api, rds, keyboard)
                    else:
                        echo(event, vk_api, keyboard)


if __name__ == '__main__':
    main()