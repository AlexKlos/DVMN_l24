import re

_QA_REGEX = re.compile(
    r'(?m)^\s*Вопрос[^\n]*\r?\n(?P<q>.*?)^\s*Ответ:\s*\r?\n(?P<a>.*?)(?=\r?\n\s*\r?\n|$)', 
    re.DOTALL
)


def get_qa_dict(filename, encoding):
    with open(filename, 'r', encoding=encoding) as f:
        text = f.read()

    return {m['q'].strip(): m['a'].strip() for m in _QA_REGEX.finditer(text)}


def cut_answer(answer):
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


def make_user_keys(user_id):
    base = f'user:{user_id}'
    return {
        'idx': f'{base}:idx',
        'q': f'{base}:current_question',
        'a': f'{base}:current_answer',
        'score': f'{base}:score',
    }
