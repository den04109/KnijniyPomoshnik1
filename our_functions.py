import os

from llm import chat, MODEL_FAST, MODEL_LARGE

books = [
    "Колобок",
    "Война и мир",
    "Преступление и наказание",
    "Муму"
]

books_folder = "books"
user_files_folder = "user_files"

STRICT_SYSTEM_PROMPT = """
Ты — справочная система. Твоя задача — давать прямой, исчерпывающий ответ на вопрос пользователя.

КРИТИЧЕСКИЕ ПРАВИЛА ФОРМАТИРОВАНИЯ:
1. ЗАПРЕЩЕНО использовать фразы: "Из представленных текстов", "В загруженных файлах", "Согласно контексту", "Основываясь на предоставленной информации", "Если же говорить о...", "В предоставленных книгах ответа нет", "Однако есть в других книгах".
2. ЗАПРЕЩЕНО описывать процесс поиска или анализировать, чего не хватает в источниках.
3. Ты должен писать так, будто знаешь ответ изначально. Никаких отсылок к тому, откуда ты взял информацию.
4. Просто напиши сам ответ. Сразу. Без вводных слов.
5. Никогда не упоминай загруженные книги, файлы, контекст, источники или их отсутствие.
6. Если вопрос звучит как "в каких книгах...", сразу перечисли конкретные книги и авторов.

Пример правильного ответа на вопрос "Какие книги развивают тему любви к родине?":
"Тему любви к родине развивают такие произведения, как «Война и мир» Л. Н. Толстого, «Герой нашего времени» М. Ю. Лермонтова, «Тарас Бульба» Н. В. Гоголя и «Капитанская дочка» А. С. Пушкина."

Пример НЕПРАВИЛЬНОГО ответа:
"Из представленных текстов только «Муму» косвенно затрагивает тему... Если же говорить о классической литературе..."
"""

FORBIDDEN_META_PHRASES = [
    "из представленных",
    "в представленных",
    "в загруженных",
    "в предоставленных",
    "согласно контексту",
    "в ваших файлах",
    "в файлах",
    "в текстах",
    "в переданном контексте",
    "в контексте",
    "ответа нет",
    "нет ответа",
    "ответ не найден",
    "не найден",
    "не найдено",
    "не содержится",
    "однако есть в других",
    "но есть в других",
    "если же говорить",
]


def _is_bad_context_answer(answer: str) -> bool:
    """True, если ответ — это отказ, мета-фраза или упоминание отсутствия в источниках."""
    if not answer:
        return True
    low = answer.lower().strip()
    if low in {"none", "нет", "нет ответа", "ответ не найден", "не найдено"}:
        return True
    return any(phrase in low for phrase in FORBIDDEN_META_PHRASES)


def get_titles_to_question(question):
    answer = chat(
        [
            {
                "role": "system",
                "content": f"""
Есть список книг:
{books}

Определи, к каким книгам относится вопрос.

Формат ответа строго:
[книга]
или
[книга1 | книга2]
или
None
"""
            },
            {"role": "user", "content": question}
        ],
        model=MODEL_FAST,
        temperature=0,
    )
    return answer if answer is not None else "None"


def get_answers_from_context(question, context_text):
    """
    Ищет ответ в переданном контексте.
    Возвращает ЧИСТЫЙ ответ или None, если ответа нет
    или модель начала ссылаться на контекст/отсутствие в нём.
    """
    if not context_text:
        return None

    answer = chat(
        [
            {
                "role": "system",
                "content": STRICT_SYSTEM_PROMPT + """

Ты работаешь с блоком <context>.
Если в <context> нет прямого ответа на вопрос, верни ровно одно слово: None.
Не пиши, что ответа нет в context.
Не сравнивай context с другими книгами.
Не упоминай context, файлы, загруженные или предоставленные книги.
"""
            },
            {
                "role": "user",
                "content": f"""
<context>
{context_text}
</context>

Вопрос: {question}
"""
            }
        ],
        model=MODEL_FAST,
        temperature=0,
    )

    if answer is None or _is_bad_context_answer(answer):
        return None

    return answer


def generate_general_answer(question):
    """
    Ответ из общих знаний модели.
    Контекст файлов сюда НЕ передаётся вообще.
    """
    answer = chat(
        [
            {
                "role": "system",
                "content": STRICT_SYSTEM_PROMPT + """

Ты отвечаешь из общих знаний.
Не упоминай никакие загруженные, предоставленные или переданные источники.
Не говори, что чего-то нет в источниках.
Если вопрос спрашивает "в каких книгах...", сразу перечисляй конкретные книги и авторов.
"""
            },
            {
                "role": "user",
                "content": question
            }
        ],
        model=MODEL_LARGE,
        temperature=0.2,
    )

    if answer is None:
        return "Извините, произошла ошибка при обращении к ИИ."

    # Если вдруг модель всё равно начала юлить — просим ответить заново жёстко
    if _is_bad_context_answer(answer):
        retry_answer = chat(
            [
                {
                    "role": "system",
                    "content": """
Ответь заново.
Запрещены любые фразы об отсутствии информации в предоставленных, загруженных или переданных книгах/файлах/контексте.
Не упоминай источники.
Просто сразу дай ответ по существу.
"""
                },
                {"role": "user", "content": question}
            ],
            model=MODEL_LARGE,
            temperature=0,
        )
        if retry_answer:
            answer = retry_answer

    return answer


def read_folder(folder_path):
    """Читает все txt файлы из папки и возвращает единый текст."""
    texts = []

    if not os.path.exists(folder_path):
        return ""

    for file in os.listdir(folder_path):
        if file.endswith(".txt"):
            path = os.path.join(folder_path, file)
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()[:12000]
            texts.append(f"--- Начало файла: {file} ---\n{text}\n--- Конец файла ---")

    return "\n\n".join(texts)


def is_general_books_question(question: str) -> bool:
    """
    Вопросы вида "в каких книгах..." лучше отвечать из общих знаний,
    иначе модель перечислит только загруженные книги.
    """
    q = question.lower()
    markers = [
        "в каких книгах",
        "какие книги",
        "в какой книге",
        "в каком произведении",
        "в каких произведениях",
        "посоветуй книг",
        "что почитать",
        "где говорится",
        "где упоминается",
    ]
    return any(marker in q for marker in markers)


def test_answer(question):
    general_books_question = is_general_books_question(question)

    # 1. Сначала ищем в загруженных книгах
    books_context = read_folder(books_folder)
    if books_context:
        answer = get_answers_from_context(question, books_context)
        # Для общих вопросов "в каких книгах..." локальный ответ не используем:
        # он будет неполным, потому что ограничен только загруженными книгами.
        if answer and not general_books_question:
            return answer

    # 2. Затем ищем в пользовательских файлах
    user_context = read_folder(user_files_folder)
    if user_context:
        answer = get_answers_from_context(question, user_context)
        if answer and not general_books_question:
            return answer

    # 3. Если локально ответа нет — отвечаем из общих знаний/условного "интернета"
    return generate_general_answer(question)


# --- ОСТАЛЬНЫЕ ФУНКЦИИ ---

def get_file_origin(file_content):
    question_text = '''Определи, какому произведению относится данный отрывок.
Ответ выведи в виде "Фамилия И. О. - Название произведения".
Например: "Достоевский Ф. М. - Преступление и наказание".
Только строго по примеру, ничего больше не пиши после точки.'''

    answer = chat(
        [
            {
                "role": "system",
                "content": "Отвечай только на основе предоставленного текста. Если информации нет в тексте — скажи, что её нет."
            },
            {
                "role": "user",
                "content": f"""Вот содержимое файла:
{file_content}

Вопрос: {question_text}
"""
            }
        ],
        model=MODEL_LARGE,
    )

    # main.py при ответе, начинающемся с "Информации о", оставляет имя файла,
    # поэтому при ошибке API возвращаем именно такую строку.
    if answer is None:
        return "Информации о произведении нет."

    return answer


def open_file_to_research_origin(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        file_content = f.read(400)

    origin = get_file_origin(file_content)
    return origin