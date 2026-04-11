import re

def clean_code(source_code):
    errors = []

    # проверка незакрытых многострочных комментариев Python
    if source_code.count('"""') % 2 != 0:
        errors.append("Ошибка: незакрытый многострочный комментарий")

    # удалить многострочные комментарии """ """
    source_code = re.sub(r'""".*?"""', '', source_code, flags=re.DOTALL)

    # удалить однострочные комментарии #
    source_code = re.sub(r'#.*', '', source_code)

    # удалить пробелы в начале и конце строк
    source_code = re.sub(r'^[ \t]+|[ \t]+$', '', source_code, flags=re.MULTILINE)

    # удалить пустые строки
    source_code = re.sub(r'\n\s*\n', '\n', source_code)

    # проверка реально проблемных символов (управляющие)
    invalid_chars = re.findall(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', source_code)
    if invalid_chars:
        errors.append("Ошибка: обнаружены управляющие символы")

    return source_code, errors


if __name__ == "__main__":
    with open("test.py", "r", encoding="utf-8") as f:
        code = f.read()

    cleaned_code, errors = clean_code(code)

    if errors:
        print("\nСообщения:")
        for e in errors:
            print(e)

    print("Очищенный код:\n")
    print(cleaned_code)
    print("Ошибок не обнаружено." if not errors else "Ошибки обнаружены.")