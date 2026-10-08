import re
import json
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
    headings = [h for h in root.find_all('h2') if re.fullmatch(r'вопрос\s+\d+', normalized(h.text()))]
    if not headings:
        raise ValueError('Не найдены вопросы в формате SyncShare')
    # SyncShare exports the quiz title in the paragraph beside the page heading.
    for heading in root.find_all('h1'):
        if normalized(heading.text()) == 'просмотр вопросов':
            page_title = next((p.text() for p in heading.parent.find_all('p') if p.text()), '')
            if page_title:
                title = page_title
            break
    questions = []
    for h in headings:
        number = int(re.search(r'\d+', h.text()).group())
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
        correctness: dict[str, bool | None] = {}
        answer_labels: dict[str, str] = {}
        conflicts: set[str] = set()
        for table in card.find_all('table'):
            headers = [normalized(th.text()) for th in table.find_all('th')]
            if 'правильность' not in headers:
                continue
            answer_col = headers.index('ответ') if 'ответ' in headers else 0
            correct_col = headers.index('правильность')
            for row in table.find_all('tr'):
                cells = row.find_all('td')
                if len(cells) <= max(answer_col, correct_col):
                    continue
                status = normalized(cells[correct_col].text())
                value = {'правильно': True, 'неправильно': False}.get(status)
                key = normalized(cells[answer_col].text())
                answer_labels.setdefault(key, cells[answer_col].text())
                source.append(f'{cells[answer_col].text()}: {cells[correct_col].text()}')
                if key in conflicts:
                    continue
                if key in correctness and correctness[key] is not None and value is not None and correctness[key] != value:
                    correctness[key] = None
                    conflicts.add(key)
                    warnings.append('Противоречивые отметки правильности')
                elif value is not None or key not in correctness:
                    correctness[key] = value
        for option in options:
            option.is_correct = correctness.get(normalized(option.text))
        question_type = 'multiple_choice' if 'checkbox' in types else 'single_choice'
        if question_type == 'single_choice' and options and not any(normalized(option.text) in conflicts for option in options):
            known_correct = [i for i, option in enumerate(options) if option.is_correct is True]
            unknown = [i for i, option in enumerate(options) if option.is_correct is None]
            known_wrong = [i for i, option in enumerate(options) if option.is_correct is False]
            if len(known_correct) == 1:
                for i in unknown:
                    options[i].is_correct = False
            elif not known_correct and len(known_wrong) == len(options) - 1 and len(unknown) == 1:
                options[unknown[0]].is_correct = True
            # A repeated answer label cannot be safely mapped to one option.
            labels = [normalized(option.text) for option in options]
            if len(labels) != len(set(labels)):
                duplicate_keys = {label for label in labels if labels.count(label) > 1}
                for option in options:
                    if normalized(option.text) in duplicate_keys:
                        option.is_correct = None
                warnings.append('Варианты с одинаковым текстом нужно проверить вручную')
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
            explicit.extend(answer_labels[key] for key, mark in correctness.items() if mark is True)
            if len(set(map(normalized, explicit))) == 1:
                q.correct_answer = explicit[0]
                q.source_answer = explicit[0]
                q.warnings = [w for w in q.warnings if 'текстовый ответ' not in w]
        # Preserve both sides of matching questions instead of discarding their tables.
        for table in card.find_all('table'):
            headers = [normalized(th.text()) for th in table.find_all('th')]
            if headers[:2] == ['левая часть', 'правая часть']:
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


def parse_json_text(source: str, filename_title: str = 'Импорт JSON') -> Preview:
    if not source.strip() or len(source) > MAX_TEXT:
        raise ValueError('JSON пустой или слишком большой')
    # Accept a fenced JSON block copied from an AI response, while still requiring
    # the file contents to be a single JSON document.
    source = re.sub(r'^\s*```(?:json)?\s*|\s*```\s*$', '', source.strip(), flags=re.I)
    try:
        data = json.loads(source)
    except json.JSONDecodeError as exc:
        raise ValueError(f'Некорректный JSON: строка {exc.lineno}, столбец {exc.colno}') from None
    if not isinstance(data, dict):
        raise ValueError('В корне JSON должен находиться объект с title и questions')
    title = data.get('title')
    title = title.strip() if isinstance(title, str) and title.strip() else filename_title
    if len(title) > 200:
        raise ValueError('Название теста должно быть не длиннее 200 символов')
    description = data.get('description', '')
    if not isinstance(description, str) or len(description) > 20000:
        raise ValueError('description должен быть строкой длиной до 20 000 символов')
    raw_questions = data.get('questions')
    if not isinstance(raw_questions, list) or not raw_questions or len(raw_questions) > 1000:
        raise ValueError('questions должен содержать от 1 до 1000 вопросов')

    allowed_types = {'single_choice', 'multiple_choice', 'text', 'fill_blank', 'matching'}
    questions = []
    for index, raw in enumerate(raw_questions, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f'Вопрос {index}: ожидался объект')
        text = raw.get('text')
        if not isinstance(text, str) or not text.strip() or len(text) > 20000:
            raise ValueError(f'Вопрос {index}: text должен быть непустой строкой до 20 000 символов')
        raw_options = raw.get('options', raw.get('answers', []))
        if not isinstance(raw_options, list) or len(raw_options) > 100:
            raise ValueError(f'Вопрос {index}: options должен быть массивом до 100 вариантов')
        options = []
        for option_index, option in enumerate(raw_options, start=1):
            if isinstance(option, str):
                option_text, is_correct = option.strip(), None
            elif isinstance(option, dict):
                option_text = option.get('text')
                is_correct = option.get('is_correct', option.get('correct'))
                if is_correct is not None and not isinstance(is_correct, bool):
                    raise ValueError(f'Вопрос {index}, вариант {option_index}: is_correct должен быть true, false или null')
            else:
                raise ValueError(f'Вопрос {index}, вариант {option_index}: ожидалась строка или объект')
            if not isinstance(option_text, str) or not option_text.strip() or len(option_text) > 20000:
                raise ValueError(f'Вопрос {index}, вариант {option_index}: text должен быть непустой строкой')
            options.append(PreviewOption(text=option_text.strip(), is_correct=is_correct))

        raw_blanks = raw.get('blanks', [])
        if not isinstance(raw_blanks, list) or len(raw_blanks) > 100:
            raise ValueError(f'Вопрос {index}: blanks должен быть массивом до 100 полей')
        blanks = []
        for blank_index, blank in enumerate(raw_blanks, start=1):
            if not isinstance(blank, dict):
                raise ValueError(f'Вопрос {index}, поле {blank_index}: ожидался объект')
            prompt = blank.get('prompt')
            answer = blank.get('correct_answer', '')
            choices = blank.get('choices', [])
            if (not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 20000
                    or not isinstance(answer, str) or len(answer) > 20000
                    or not isinstance(choices, list) or len(choices) > 100
                    or any(not isinstance(choice, str) or len(choice) > 20000 for choice in choices)):
                raise ValueError(f'Вопрос {index}, поле {blank_index}: проверь prompt, correct_answer и choices')
            blanks.append({'prompt': prompt.strip(), 'correct_answer': answer.strip(), 'choices': [c.strip() for c in choices if c.strip()]})

        kind = raw.get('question_type', raw.get('type'))
        if kind is None:
            kind = 'multiple_choice' if sum(option.is_correct is True for option in options) > 1 else 'single_choice' if options else 'fill_blank' if blanks else 'text'
        if not isinstance(kind, str) or kind not in allowed_types:
            raise ValueError(f'Вопрос {index}: неизвестный question_type {kind!r}')
        correct_answer = raw.get('correct_answer', '')
        explanation = raw.get('explanation', '')
        if not isinstance(correct_answer, str) or len(correct_answer) > 20000 or not isinstance(explanation, str) or len(explanation) > 20000:
            raise ValueError(f'Вопрос {index}: correct_answer и explanation должны быть строками')
        number = raw.get('number', index)
        if not isinstance(number, int) or isinstance(number, bool) or number < 1:
            raise ValueError(f'Вопрос {index}: number должен быть положительным целым числом')
        warnings = raw.get('warnings', [])
        if not isinstance(warnings, list) or any(not isinstance(warning, str) for warning in warnings):
            warnings = []
        if kind in ('single_choice', 'multiple_choice'):
            if len(options) < 2:
                warnings.append('Добавьте не менее двух вариантов ответа.')
            if any(option.is_correct is None for option in options):
                warnings.append('Правильность некоторых вариантов не указана: проверьте их в превью.')
            if kind == 'single_choice' and sum(option.is_correct is True for option in options) > 1:
                warnings.append('Для одиночного выбора отмечено несколько правильных ответов.')
            if not any(option.is_correct is True for option in options):
                warnings.append('Отметьте правильный вариант в превью.')
        elif kind == 'text' and not correct_answer.strip():
            warnings.append('Добавьте правильный текстовый ответ в превью.')
        elif kind in ('fill_blank', 'matching') and (not blanks or any(not blank['prompt'] or not blank['correct_answer'] for blank in blanks)):
            warnings.append('Заполните подпись и правильный ответ для каждого поля.')

        questions.append(PreviewQuestion(
            number=number, text=text.strip(), question_type=kind,
            options=options, correct_answer=correct_answer.strip(), blanks=blanks,
            explanation=explanation.strip(), source_answer=str(raw.get('source_answer', '')),
            warnings=warnings,
        ))
    return Preview(title=title, description=description.strip(), source='json_import', questions=questions)


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
