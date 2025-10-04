from environs import env
import redis
from telegram import ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

from quiz_bot_shared_utils import get_qa_dict, cut_answer, normalize_answer


def start(update, context):
    update.message.reply_text(
        'Привет! Я бот для викторин!',
        reply_markup=main_keyboard()
    )


def handle_text(update, context):
    user_id = update.effective_user.id
    r = context.bot_data['redis']
    answer_key = f'user:{user_id}:current_answer'
    if not r.get(answer_key):
        return

    check_answer(update, context)


def ask_new_question(update, context):
    user_id = update.effective_user.id
    r = context.bot_data['redis']
    quiz_items = context.bot_data['quiz_items']

    idx_key = f'user:{user_id}:idx'
    question_key = f'user:{user_id}:current_question'
    answer_key = f'user:{user_id}:current_answer'

    if not quiz_items:
        update.message.reply_text('Нет вопросов')

    idx = r.get(idx_key)
    idx = int(idx) if idx is not None else 0
    if idx >= len(quiz_items):
        idx = 0

    question, full_answer = quiz_items[idx]
    short_answer = cut_answer(full_answer)

    r.set(question_key, question)
    r.set(answer_key, short_answer)
    r.set(idx_key, idx + 1)

    update.message.reply_text(
        question.strip(),
        reply_markup=main_keyboard()
    )


def check_answer(update, context):
    user_id = update.effective_user.id
    r = context.bot_data['redis']

    question_key = f'user:{user_id}:current_question'
    answer_key = f'user:{user_id}:current_answer'
    score_key = f'user:{user_id}:score'

    expected = r.get(answer_key) or ''
    user_text = update.message.text or ''

    if normalize_answer(user_text) == normalize_answer(expected):
        r.incr(score_key, 1)
        update.message.reply_text(
            'Правильно! Поздравляю! Для следующего вопроса нажми «Новый вопрос»',
            reply_markup=main_keyboard()
        )
        r.delete(question_key)
        r.delete(answer_key)
    else:
        update.message.reply_text(
            'Неправильно… Попробуешь ещё раз?',
            reply_markup=main_keyboard()
        )


def give_up(update, context):
    user_id = update.effective_user.id
    r = context.bot_data['redis']
    answer_key = f'user:{user_id}:current_answer'
    correct = r.get(answer_key)

    if correct:
        update.message.reply_text(f'Правильный ответ: {correct}', reply_markup=main_keyboard())
    else:
        update.message.reply_text('Вопрос не был задан', reply_markup=main_keyboard())

    ask_new_question(update, context)


def show_score(update, context):
    user_id = update.effective_user.id
    r = context.bot_data['redis']
    score_key = f'user:{user_id}:score'
    score_val = r.get(score_key)
    score = int(score_val) if score_val is not None else 0

    update.message.reply_text(f'Твой счёт: {score}', reply_markup=main_keyboard())


def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[['Новый вопрос', 'Сдаться'], ['Мой счёт']],
        resize_keyboard=True,
        one_time_keyboard=False
    )


def main():
    env.read_env()
    tg_bot_token = env.str('TG_BOT_TOKEN')
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

    updater = Updater(tg_bot_token, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.bot_data['quiz_items'] = quiz_items
    dispatcher.bot_data['redis'] = r


    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(MessageHandler(Filters.regex('^Новый вопрос$'), ask_new_question))
    dispatcher.add_handler(MessageHandler(Filters.regex('^Сдаться$'), give_up))
    dispatcher.add_handler(MessageHandler(Filters.regex('^Мой счёт$'), show_score))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
