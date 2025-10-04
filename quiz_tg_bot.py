from environs import env
import redis
from telegram import ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler

from quiz_bot_shared_utils import get_qa_dict, cut_answer, normalize_answer

ASKING = 1


def start(update, context):
    update.message.reply_text(
        'Привет! Я бот для викторин!',
        reply_markup=main_keyboard()
    )


def echo(update, context):
    update.message.reply_text(
        update.message.text,
        reply_markup=main_keyboard()
    )


def ask_new_question(update, context):
    user_id = update.effective_user.id
    rds = context.bot_data['redis']
    quiz_items = context.bot_data['quiz_items']

    idx_key = f'user:{user_id}:idx'
    question_key = f'user:{user_id}:current_question'
    answer_key = f'user:{user_id}:current_answer'

    if not quiz_items:
        update.message.reply_text('Нет вопросов')
        return ConversationHandler.END

    idx = rds.get(idx_key)
    idx = int(idx) if idx is not None else 0
    if idx >= len(quiz_items):
        idx = 0

    question, full_answer = quiz_items[idx]
    short_answer = cut_answer(full_answer)

    rds.set(question_key, question)
    rds.set(answer_key, short_answer)
    rds.set(idx_key, idx + 1)

    update.message.reply_text(
        question.strip(),
        reply_markup=main_keyboard()
    )

    return ASKING


def check_answer(update, context):
    user_id = update.effective_user.id
    rds = context.bot_data['redis']

    question_key = f'user:{user_id}:current_question'
    answer_key = f'user:{user_id}:current_answer'
    score_key = f'user:{user_id}:score'

    expected = rds.get(answer_key) or ''
    user_text = update.message.text or ''

    if normalize_answer(user_text) == normalize_answer(expected):
        rds.incr(score_key, 1)
        update.message.reply_text(
            'Правильно! Поздравляю! Для следующего вопроса нажми «Новый вопрос»',
            reply_markup=main_keyboard()
        )
        rds.delete(question_key)
        rds.delete(answer_key)
        return ConversationHandler.END
    else:
        update.message.reply_text(
            'Неправильно… Попробуешь ещё раз?',
            reply_markup=main_keyboard()
        )
        return ASKING


def give_up(update, context):
    user_id = update.effective_user.id
    rds = context.bot_data['redis']

    answer_key = f'user:{user_id}:current_answer'
    correct = rds.get(answer_key)

    if correct:
        update.message.reply_text(f'Правильный ответ: {correct}', reply_markup=main_keyboard())
    else:
        update.message.reply_text('Вопрос не был задан', reply_markup=main_keyboard())

    return ask_new_question(update, context)


def show_score(update, context):
    user_id = update.effective_user.id
    rds = context.bot_data['redis']
    score_key = f'user:{user_id}:score'
    score_val = rds.get(score_key)
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
    TG_BOT_TOKEN = env.str('TG_BOT_TOKEN')
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

    updater = Updater(TG_BOT_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.bot_data['quiz_items'] = quiz_items
    dispatcher.bot_data['redis'] = rds

    conv = ConversationHandler(
        entry_points=[MessageHandler(Filters.regex('^Новый вопрос$'), ask_new_question)],
        states={
            ASKING: [
                MessageHandler(Filters.regex('^Сдаться$'), give_up),
                MessageHandler(Filters.regex('^Мой счёт$'), show_score),
                MessageHandler(Filters.text & ~Filters.command, check_answer),
            ]
        },
        fallbacks=[
            CommandHandler('start', start),
            MessageHandler(Filters.regex('^Мой счёт$'), show_score),
            MessageHandler(Filters.regex('^Сдаться$'), give_up),
        ],
        per_user=True,
        per_chat=True,
    )

    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(conv)
    dispatcher.add_handler(MessageHandler(Filters.regex('^Мой счёт$'), show_score))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, echo))

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
