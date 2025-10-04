import re

def get_qa_dict(filename, encoding):
    with open(filename, 'r', encoding=encoding) as file:
        lines = file.readlines()

    line_flag = 0
    text_buffer = ''
    question = ''
    answer = ''
    quiz = {}
    for line in lines:
        if line_flag != 0:
            text_buffer += line

        match line[:6].strip():
            case 'Вопрос':
                line_flag = 1
                text_buffer = ''
            case 'Ответ:':
                line_flag = 2
                text_buffer = ''
            case '':
                if line_flag == 1:
                    question = text_buffer
                elif line_flag == 2:
                    answer = text_buffer
                    quiz[question] = answer
                line_flag = 0

    return quiz


def cut_answer(answer):
    if not answer:
        return ''
    a = answer.strip()
    p_dot = a.find('.')
    p_par = a.find('(')
    cuts = [p for p in (p_dot, p_par) if p != -1]
    if cuts:
        a = a[: min(cuts)]

    return a.strip()


def normalize_answer(text):
    if not text:
        return ''
    processed_text = text.strip().lower()
    processed_text = processed_text.replace('ё', 'е')
    processed_text = processed_text.strip(' "\'“”«»‘’.!?…')
    processed_text = re.sub(r'\s+', ' ', processed_text)

    return processed_text
