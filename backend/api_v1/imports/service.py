import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

from .html_tree import TreeParser
from .schemas import Preview, PreviewOption, PreviewQuestion

MAX_BYTES = 8 * 1024 * 1024
MAX_TEXT = 2_000_000


def normalized(value: str) -> str:
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', value).replace('\u00ad', '')).strip().casefold().rstrip('.;')


def match_answers(options: list[str], answer: str) -> tuple[list[bool | None], list[str]]:
    """Only unambiguous exact text (or explicit leading acronym) is authoritative."""
    parts = [normalized(p) for p in answer.split(';') if p.strip()]
    matched = set()
    warnings = []
    for part in parts:
        hits = [i for i, option in enumerate(options) if normalized(option) == part]
        if not hits and re.fullmatch(r'[a-z][a-z0-9]{1,10}', part):
            hits = [i for i, option in enumerate(options)
                    if re.split(r'\s+[–—-]\s+', normalized(option))[0] == part]
        if len(hits) == 1:
            matched.add(hits[0])
        else:
            warnings.append(f'Не удалось однозначно сопоставить ответ: {part}')
    if not parts:
        warnings.append('Правильный ответ не указан')
    return [True if i in matched else (None if warnings else False) for i in range(len(options))], warnings


def parse_pdf_text(text: str, title: str = 'Импорт PDF') -> Preview:
    text = text.replace('\r', '').replace('\u00ad', '')
    text = re.sub(r'^PAGE \d+\s*$', '', text, flags=re.M)
    if not text.strip() or len(text) > MAX_TEXT:
        raise ValueError('PDF пустой, слишком большой или не содержит доступного текста')
    # Question and option numbers overlap. A new question is sought only after Ответ:.
    blocks = []
    first = re.search(r'^\s*1\.\s+', text, re.M)
    if not first:
        raise ValueError('Не найден поддерживаемый формат вопросов PDF')
    start = first.start()
    number = 1
    while True:
        answer = re.search(r'^\s*Ответ\s*:', text[start:], re.M | re.I)
        if not answer:
            raise ValueError(f'Не найден блок Ответ: для вопроса {number}')
        after_answer = start + answer.end()
        next_question = re.search(rf'^\s*{number + 1}\.\s+', text[after_answer:], re.M)
        end = after_answer + next_question.start() if next_question else len(text)
        blocks.append((number, text[start:end]))
        if not next_question:
            break
        start, number = end, number + 1
        if number > 1000:
            raise ValueError('Слишком много вопросов')
    if len(re.findall(r'^\s*Ответ\s*:', text, re.M | re.I)) != len(blocks):
        raise ValueError('Нарушена последовательность номеров вопросов PDF; проверьте исходный файл')
    questions = []
    for number, block in blocks:
        if block.count('Варианты ответа:') > 1:
            raise ValueError('Нарушена последовательность номеров вопросов PDF')
        body, answer = re.split(r'\bОтвет\s*:', block, maxsplit=1, flags=re.I)
        explanation = ''
        if re.search(r'Пояснение\s*:', answer):
            answer, explanation = re.split(r'Пояснение\s*:', answer, maxsplit=1)
        answer, explanation = ' '.join(answer.split()), ' '.join(explanation.split())
        body = re.sub(r'^\s*\d+\.\s*', '', body)
        options = []
        warnings = []
        if 'Варианты ответа:' in body:
            body, option_text = body.split('Варианты ответа:', 1)
            options = [' '.join(p.split()) for p in re.split(r'^\s*\d+\.\s+', option_text, flags=re.M)[1:]]
        question_text = ' '.join(body.split())
        if options:
            marks, warnings = match_answers(options, answer)
            kind = 'multiple_choice' if sum(m is True for m in marks) > 1 or ';' in answer else 'single_choice'
            if len(options) < 2:
                warnings.append('Найден только один вариант: добавьте варианты или выберите текстовый ответ')
            q = PreviewQuestion(number=number, text=question_text, question_type=kind,
                options=[PreviewOption(text=o, is_correct=m) for o, m in zip(options, marks)],
                source_answer=answer, explanation=explanation, warnings=warnings)
        else:
            q = PreviewQuestion(number=number, text=question_text, question_type='text',
                correct_answer=answer, source_answer=answer, explanation=explanation)
            if '[пропуск]' in question_text.casefold():
                prompts = [p.strip() for p in answer.split(';') if p.strip()]
                blanks = []
                for part in prompts:
                    pair = re.split(r'\s+[—–]\s+', part, maxsplit=1)
                    if len(pair) == 2:
                        blanks.append(dict(prompt=pair[0], correct_answer=pair[1].rstrip('.')))
                if len(blanks) == question_text.casefold().count('[пропуск]'):
                    q.question_type, q.blanks, q.correct_answer = 'fill_blank', blanks, ''
                    q.warnings.append('Проверьте порядок пропусков и единицы измерения ответов')
                else:
                    q.warnings.append('Задание с пропусками: проверьте разбиение на поля ответа')
        if not answer:
            q.warnings.append('Правильный ответ не указан')
        questions.append(q)
    return Preview(title=title, source='pdf_import', questions=questions)


def parse_html(html: str, title: str = 'Импорт HTML') -> Preview:
    if not html.strip() or len(html) > MAX_TEXT:
        raise ValueError('HTML пустой или слишком большой')
    parser = TreeParser()
    parser.feed(html)
    root = parser.root
    headings = [h for h in root.find_all('h2') if re.fullmatch(r'Вопрос\s+\d+', h.text())]
    if not headings:
        raise ValueError('Не найдены вопросы в формате SyncShare')
    questions = []
    for h in headings:
        number = int(h.text().split()[-1])
        card = h.parent
        while card.parent and 'overflow-hidden' not in card.attrs.get('class', '').split():
            card = card.parent
        paragraphs = card.find_all('p')
        if not paragraphs:
            raise ValueError(f'Нет текста вопроса {number}')
        body = paragraphs[0].text()
        inputs = card.find_all('input')
        options = []
        types = set()
        for field in inputs:
            kind = field.attrs.get('type')
            if kind not in ('checkbox', 'radio'):
                continue
            types.add(kind)
            row = field.parent
            while row is not card and not row.find_all('label'):
                row = row.parent
            labels = row.find_all('label')
            if labels:
                options.append(PreviewOption(text=labels[0].text()))
        warnings = []
        source = []
        # Selected inputs and vote counts are NOT an answer key.
        correctness = {}
        for table in card.find_all('table'):
            headers = [th.text().casefold() for th in table.find_all('th')]
            if 'правильность' not in headers:
                continue
            answer_col = headers.index('ответ') if 'ответ' in headers else 0
            correct_col = headers.index('правильность')
            for row in table.find_all('tr'):
                cells = row.find_all('td')
                if len(cells) <= max(answer_col, correct_col):
                    continue
                status = cells[correct_col].text().casefold()
                value = {'правильно': True, 'неправильно': False}.get(status)
                key = normalized(cells[answer_col].text())
                source.append(f'{cells[answer_col].text()}: {cells[correct_col].text()}')
                if key in correctness and correctness[key] != value:
                    correctness[key] = None
                    warnings.append('Противоречивые отметки правильности')
                else:
                    correctness[key] = value
        for option in options:
            option.is_correct = correctness.get(normalized(option.text))
        question_type = 'multiple_choice' if 'checkbox' in types else 'single_choice'
        if not options:
            fields = [i for i in inputs if i.attrs.get('type') == 'text']
            question_type = 'fill_blank' if len(fields) > 1 else 'text'
            warnings.append('Правильный текстовый ответ нужно проверить и заполнить вручную')
        elif any(o.is_correct is None for o in options):
            warnings.append('В HTML нет подтверждённой правильности всех вариантов; проверьте вручную')
        if card.find_all('img'):
            warnings.append('Вопрос содержит изображение: файл изображения не импортирован')
        q = PreviewQuestion(number=number, text=body, question_type=question_type,
            options=options, source_answer='; '.join(source), warnings=warnings)
        if question_type == 'fill_blank':
            q.blanks = [dict(prompt=f'Пропуск {i+1}', correct_answer='') for i in range(len(fields))]
        # Text answer keys have a dedicated block, separate from vote statistics.
        if not options and question_type == 'text':
            explicit = []
            for heading in card.find_all('h3'):
                if heading.text() == 'Правильный ответ':
                    values = [p.text() for p in heading.parent.find_all('p')]
                    explicit.extend(v for v in values if v and v != 'Правильного ответа нет')
            explicit.extend(cells for cells, mark in correctness.items() if mark is True)
            if len(set(map(normalized, explicit))) == 1:
                q.correct_answer = explicit[0]
                q.source_answer = explicit[0]
                q.warnings = [w for w in q.warnings if 'текстовый ответ' not in w]
        # Preserve both sides of matching questions instead of discarding their tables.
        for table in card.find_all('table'):
            headers = [th.text() for th in table.find_all('th')]
            if headers == ['Левая часть', 'Правая часть']:
                choices = []
                for heading in card.find_all('h3'):
                    if heading.text() == 'Варианты правой части':
                        choices = [li.text().lstrip('• ').strip() for li in heading.parent.find_all('li')]
                q.question_type = 'matching'
                q.blanks = []
                for row in table.find_all('tr'):
                    cells = row.find_all('td')
                    if len(cells) == 2:
                        q.blanks.append(dict(prompt=cells[0].text(), correct_answer='', choices=choices))
                q.warnings = ['Задание на сопоставление: подтвердите правильную пару для каждой строки']
        questions.append(q)
    warnings = []
    declared = re.search(r'Вопросов в тесте:\s*(\d+)', root.text())
    if declared and int(declared[1]) != len(questions):
        warnings.append(f'В файле заявлено {declared[1]} вопросов, найдено {len(questions)}')
    return Preview(title=title, source='html_import', questions=questions, warnings=warnings)


def extract_pdf(data: bytes) -> str:
    if not data.startswith(b'%PDF-'):
        raise ValueError('Файл не является PDF')
    with tempfile.TemporaryDirectory(prefix='quiz-pdf-') as directory:
        source = Path(directory) / 'input.pdf'
        source.write_bytes(data)
        if shutil.which('pdftotext'):
            command = ['pdftotext', '-enc', 'UTF-8', str(source), '-']
        elif sys.platform == 'darwin' and shutil.which('swift'):
            command = ['swift', '-module-cache-path', str(Path(tempfile.gettempdir()) / 'quiz-swift-cache'),
                       str(Path(__file__).with_name('extract_pdf.swift')), str(source)]
        else:
            raise RuntimeError('Для PDF установите Poppler (pdftotext); он включён в Dockerfile')
        try:
            result = subprocess.run(command, capture_output=True, timeout=45, check=True)
        except (subprocess.SubprocessError, OSError) as exc:
            raise ValueError('Не удалось прочитать PDF: повреждён, зашифрован или превышено время обработки') from exc
        if len(result.stdout) > MAX_TEXT * 4:
            raise ValueError('Слишком много текста в PDF')
        text = result.stdout.decode('utf-8')
        if not text.strip():
            raise ValueError('В PDF нет текстового слоя; сканирование/OCR пока не поддерживается')
        return text.replace('\f', '\n')
