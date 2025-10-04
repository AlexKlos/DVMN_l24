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



def user_keys(user_id):
    base = f'user:{user_id}'
    return {
        'idx': f'{base}:idx',
        'q': f'{base}:current_question',
        'a': f'{base}:current_answer',
        'score': f'{base}:score',
    }


def ask_new_question(event, vk_api, r, quiz_items, keyboard):
    keys = user_keys(event.user_id)
    if not quiz_items:
        send(vk_api, event.user_id, 'Нет вопросов', keyboard)
        return
    
    raw_idx = r.get(keys['idx'])
    idx = int(raw_idx) if raw_idx is not None else 0
    if idx >= len(quiz_items):
        idx = 0
    question, full_answer = quiz_items[idx]
    short_answer = cut_answer(full_answer)
    r.set(keys['q'], question)
    r.set(keys['a'], short_answer)
    r.set(keys['idx'], idx + 1)
    send(vk_api, event.user_id, question.strip(), keyboard)


def check_answer(event, vk_api, r, keyboard):
    keys = user_keys(event.user_id)
    expected = r.get(keys['a']) or ''
    user_text = event.text or ''
    if normalize_answer(user_text) == normalize_answer(expected):
        r.incr(keys['score'], 1)
        send(
            vk_api,
            event.user_id,
            'Правильно! Поздравляю! Для следующего вопроса нажми «Новый вопрос»',
            keyboard,
        )
        r.delete(keys['q'])
        r.delete(keys['a'])
    else:
        send(vk_api, event.user_id, 'Неправильно… Попробуешь ещё раз?', keyboard)


def give_up(event, vk_api, r, quiz_items, keyboard):
    keys = user_keys(event.user_id)
    correct = r.get(keys['a'])
    if correct:
        send(vk_api, event.user_id, f'Правильный ответ: {correct}', keyboard)
    else:
        send(vk_api, event.user_id, 'Вопрос не был задан', keyboard)
    ask_new_question(event, vk_api, r, quiz_items, keyboard)


def show_score(event, vk_api, r, keyboard):
    keys = user_keys(event.user_id)
    raw = r.get(keys['score'])
    score = int(raw) if raw is not None else 0
    send(vk_api, event.user_id, f'Твой счёт: {score}', keyboard)


def main():
    env.read_env()
    vk_token = env.str('VK_TOKEN')
    redis_host = env.str('REDIS_HOST')
    redis_port = env.int('REDIS_PORT')
    redis_db = env.int('REDIS_DB', 0)
    redis_pass = env.str('REDIS_PASSWORD')
    quiz_file = env.str('QUIZ_FILE')
    encoding = env.str('ENCODING')

    quiz = get_qa_dict(quiz_file, encoding)
    quiz_items = list(quiz.items())

    r = redis.Redis(
        host=redis_host,
        port=redis_port,
        db=redis_db,
        password=redis_pass,
        decode_responses=True,
    )

    vk_session = vk.VkApi(token=vk_token)
    vk_api = vk_session.get_api()

    keyboard = make_keyboard()
    longpoll = VkLongPoll(vk_session)
    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            text = (event.text or '').strip()
            keys = user_keys(event.user_id)
    
            match text:
                case 'Новый вопрос':
                    ask_new_question(event, vk_api, r, quiz_items, keyboard)
                case 'Сдаться':
                    give_up(event, vk_api, r, quiz_items, keyboard)
                case 'Мой счёт':
                    show_score(event, vk_api, r, keyboard)
                case _:
                    if r.get(keys['a']):
                        check_answer(event, vk_api, r, keyboard)
                    else:
                        pass


if __name__ == '__main__':
    main()