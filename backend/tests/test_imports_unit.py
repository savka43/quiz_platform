from pathlib import Path

import pytest
from pydantic import ValidationError

from api_v1.imports.service import parse_pdf_text, parse_html, match_answers
from api_v1.editor.schemas import QuestionInput
from api_v1.practice.schemas import AnswerInput
from api_v1.practice.service import evaluate, public_snapshot
from core.models import AttemptQuestion


def pdf_question(number=1, answer='Beta'):
    return f'{number}. Вопрос?\nВарианты ответа:\n1. Alpha\n2. Beta\nОтвет: {answer}\n'


def html_question(inputs, extra=''):
    return f'<div class="overflow-hidden"><h2>Вопрос 1</h2><p>Вопрос?</p>{inputs}{extra}</div>'


def option(text, type='radio', checked=''):
    return f'<div><div><input type="{type}" {checked}></div><label>{text}</label></div>'


def test_pdf_questions_and_options_have_independent_numbers():
    p = parse_pdf_text(pdf_question() + pdf_question(2, 'Alpha; Beta'))
    assert len(p.questions) == 2
    assert [o.is_correct for o in p.questions[0].options] == [False, True]
    assert p.questions[1].question_type == 'multiple_choice'
    assert p.response()['questions'][1]['correct_option_count'] == 2


def test_pdf_page_breaks_and_explanation():
    p = parse_pdf_text('1. Вопрос\nPAGE 2\nс переносом?\nВарианты ответа:\n1. Alpha\n2. Beta\nОтвет: Beta\nПояснение: Причина.')
    assert p.questions[0].text == 'Вопрос с переносом?'
    assert p.questions[0].explanation == 'Причина.'


@pytest.mark.parametrize('answer', ['Неизвестный вариант', '2', 'Alpha; нет'])
def test_pdf_uncertain_keys_are_not_guessed(answer):
    q = parse_pdf_text(pdf_question(answer=answer)).questions[0]
    assert q.needs_review
    assert any(o.is_correct is None for o in q.options)


def test_pdf_acronyms_and_unicode():
    flags, warnings = match_answers(['PERS — квалификация', 'RCPX – сложность', 'ТЕСТ'], 'pers; тест')
    assert flags == [True, False, True]
    assert not warnings


def test_pdf_duplicate_option_text_is_ambiguous():
    flags, warnings = match_answers(['Alpha', 'Alpha'], 'Alpha')
    assert flags == [None, None]
    assert warnings


def test_pdf_blanks():
    q = parse_pdf_text('1. Первый [пропуск], второй [пропуск]\nОтвет: Первый — 2; Второй — 3.').questions[0]
    assert q.question_type == 'fill_blank'
    assert [b['correct_answer'] for b in q.blanks] == ['2', '3']
    assert q.needs_review


@pytest.mark.parametrize('text', ['', 'произвольный документ', '1. Q без ответа', pdf_question()+pdf_question(3)])
def test_bad_pdf_format(text):
    with pytest.raises(ValueError):
        parse_pdf_text(text)


def test_html_checked_and_votes_are_not_correctness():
    q = parse_html(html_question(option('A', checked='checked')+option('B'),
        '<table><tr><th>Ответ</th><th>За</th><th>Против</th></tr><tr><td>A</td><td>100</td><td>0</td></tr></table>')).questions[0]
    assert [o.is_correct for o in q.options] == [None, None]
    assert q.needs_review


def test_html_explicit_correctness():
    stats = '<table><tr><th>Ответ</th><th>Выбрали этот вариант</th><th>Правильность</th></tr><tr><td>A</td><td>1</td><td>Правильно</td></tr><tr><td>B</td><td>5</td><td>Неправильно</td></tr></table>'
    q = parse_html(html_question(option('A')+option('B'), stats)).questions[0]
    assert [o.is_correct for o in q.options] == [True, False]
    assert not q.needs_review


def test_syncshare_single_choice_infers_only_from_an_explicit_key():
    markup = '''<main><div><h1>Просмотр вопросов</h1><p>Модуль 1</p></div>
    <div class="overflow-hidden"><h2>Вопрос 1</h2><p>Выберите ответ</p>
    <div><input type="radio"><label>A</label></div><div><input type="radio"><label>B</label></div>
    <div><input type="radio"><label>C</label></div>
    <table><tr><th>Ответ</th><th>Выбрали этот вариант</th><th>Правильность</th></tr>
    <tr><td>B</td><td>1</td><td>Правильно</td></tr></table></div></main>'''
    preview = parse_html(markup, 'wrong filename')
    assert preview.title == 'Модуль 1'
    assert [o.is_correct for o in preview.questions[0].options] == [False, True, False]
    assert not preview.questions[0].needs_review


def test_syncshare_unknown_status_is_not_treated_as_a_key():
    markup = html_question(option('A') + option('B'), '''<table><tr><th>Ответ</th><th>Правильность</th></tr>
    <tr><td>A</td><td>Неизвестно</td></tr></table>''')
    q = parse_html(markup).questions[0]
    assert [o.is_correct for o in q.options] == [None, None]
    assert q.needs_review


def test_syncshare_infers_last_single_choice_after_all_other_options_are_wrong():
    markup = html_question(option('A') + option('B') + option('C'), '''<table><tr><th>Ответ</th><th>Правильность</th></tr>
    <tr><td>A</td><td>Неправильно</td></tr><tr><td>B</td><td>Неправильно</td></tr></table>''')
    q = parse_html(markup).questions[0]
    assert [o.is_correct for o in q.options] == [False, False, True]
    assert not q.needs_review


def test_html_text_key():
    key = '<div><h3>Правильный ответ</h3><p>Текст</p></div>'
    q = parse_html(html_question('', key)).questions[0]
    assert q.correct_answer == 'Текст'
    assert not q.needs_review


def test_html_mathjax_not_duplicated():
    math = '<mjx-container><mjx-math>WRONG_DUPLICATE</mjx-math><math><msup><mi>x</mi><mn>2</mn></msup></math></mjx-container>'
    q = parse_html(html_question(option(math)+option('0'))).questions[0]
    assert 'WRONG' not in q.options[0].text
    assert '(x)^(2)' in q.options[0].text


def test_html_matching_preserves_both_sides():
    body = '<table><tr><th>Левая часть</th><th>Правая часть</th></tr><tr><td>Условие</td><td>[нет рекомендации]</td></tr></table><div><h3>Варианты правой части</h3><ul><li>• Один</li><li>• Два</li></ul></div>'
    q = parse_html(html_question('', body)).questions[0]
    assert q.question_type == 'matching'
    assert q.blanks[0]['choices'] == ['Один', 'Два']
    assert q.blanks[0]['prompt'] == 'Условие'
    assert q.needs_review


def test_html_scripts_never_become_question_text():
    q = parse_html(html_question(option('A<script>alert(1)</script>')+option('B'))).questions[0]
    assert q.options[0].text == 'A'


@pytest.mark.parametrize('html', ['', '<html><p>No questions</p></html>'])
def test_unsupported_html(html):
    with pytest.raises(ValueError):
        parse_html(html)


@pytest.mark.parametrize('data', [
    {'text':'Q', 'question_type':'single_choice', 'options':[{'text':'A','is_correct':True}]},
    {'text':'Q', 'question_type':'single_choice', 'options':[{'text':'A','is_correct':True},{'text':'B','is_correct':True}]},
    {'text':'Q', 'question_type':'multiple_choice', 'options':[{'text':'A','is_correct':False},{'text':'B','is_correct':False}]},
    {'text':'Q','correct_answer':''}, {'text':'   ','correct_answer':'A'},
    {'text':'Q', 'question_type':'fill_blank','blanks':[]},
    {'text':'Q','correct_answer':'A','owner_id':1},
])
def test_confirm_requires_valid_edited_content(data):
    with pytest.raises(ValidationError):
        QuestionInput(**data)


def test_multi_choice_requires_exact_set():
    payload = {'question_type':'multiple_choice','options':[{'id':1,'is_correct':True},{'id':2,'is_correct':True},{'id':3,'is_correct':False}]}
    assert evaluate(payload, AnswerInput(question_id=1, selected_option_ids=[2,1]))
    assert not evaluate(payload, AnswerInput(question_id=1, selected_option_ids=[1]))
    assert not evaluate(payload, AnswerInput(question_id=1, selected_option_ids=[1,2,3]))


def test_foreign_option_rejected():
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        evaluate({'question_type':'single_choice','options':[{'id':1,'is_correct':True}]}, AnswerInput(question_id=1,selected_option_ids=[99]))


def test_text_and_blank_scoring():
    assert evaluate({'question_type':'text','correct_answer':'Правильный ответ'}, AnswerInput(question_id=1,user_answer='  ПРАВИЛЬНЫЙ   ответ '))
    assert evaluate({'question_type':'fill_blank','blanks':[{'correct_answer':'2'}, {'correct_answer':'3'}]}, AnswerInput(question_id=1,blank_answers=['2','3']))


def test_snapshot_output_does_not_expose_answers():
    q=AttemptQuestion(id=10,attempt_id=1,source_question_id=5,position=0,payload={
        'text':'Q','question_type':'single_choice','correct_answer':'secret','explanation':'secret',
        'options':[{'id':1,'text':'A','is_correct':True}], 'blanks':[{'prompt':'B','correct_answer':'secret'}]})
    result = public_snapshot(q)
    assert 'secret' not in str(result)
    assert 'is_correct' not in str(result)


def test_connection_url_escapes_password():
    from core.config import Settings
    from sqlalchemy.engine import make_url
    config=Settings(postgres_user='user',postgres_password='p@ss:/%word',postgres_db='db',_env_file=None)
    assert make_url(config.database_url).password == 'p@ss:/%word'


def test_matching_requires_listed_choices():
    from fastapi import HTTPException
    payload={'question_type':'matching','blanks':[{'prompt':'Q','correct_answer':'A','choices':['A','B']}]}
    assert evaluate(payload,AnswerInput(question_id=1,blank_answers=['A']))
    assert not evaluate(payload,AnswerInput(question_id=1,blank_answers=['B']))
    with pytest.raises(HTTPException):
        evaluate(payload,AnswerInput(question_id=1,blank_answers=['missing']))
