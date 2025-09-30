from environs import env
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters


def start(update, context):
    update.message.reply_text('Здравствуйте!')


def echo(update, context):
    update.message.reply_text(update.message.text)


def main():
    env.read_env()
    TG_BOT_TOKEN = env.str('TG_BOT_TOKEN')
    updater = Updater(TG_BOT_TOKEN, use_context=True)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler("start", start))

    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, echo))
    updater.start_polling()
    updater.idle()

    # with open('quiz-questions/1vs1201.txt', 'r', encoding='koi8-r') as file:
    #     lines = file.readlines()

    # line_flag = 0
    # text_buffer = ''
    # question = ''
    # answer = ''
    # quiz = {}
    # for line in lines:
    #     if line_flag != 0:
    #         text_buffer += line

    #     match line[:6].strip():
    #         case 'Вопрос':
    #             line_flag = 1
    #             text_buffer = ''
    #         case 'Ответ:':
    #             line_flag = 2
    #             text_buffer = ''
    #         case '':
    #             if line_flag == 1:
    #                 question = text_buffer
    #             elif line_flag == 2:
    #                 answer = text_buffer
    #                 quiz[question] = answer
    #             line_flag = 0


if __name__ == '__main__':
    main()
