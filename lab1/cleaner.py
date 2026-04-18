import re
import sys


def check_comments(code):
    errors = []

    i = 0
    n = len(code)
    state = "NORMAL"

    while i < n:
        c = code[i]
        nxt = code[i + 1] if i + 1 < n else ''

        if state == "NORMAL":
            if c == '"':
                state = "IN_STRING"
            elif c == "'":
                state = "IN_CHAR"
            elif c == '/' and nxt == '/':
                state = "IN_SINGLE_COMMENT"
                i += 1
            elif c == '/' and nxt == '*':
                state = "IN_MULTI_COMMENT"
                i += 1
            elif c == '*' and nxt == '/':
                errors.append("Ошибка: найдено '*/' без соответствующего '/*'")
                return errors

        elif state == "IN_STRING":
            if c == '\\':
                i += 1
            elif c == '"':
                state = "NORMAL"

        elif state == "IN_CHAR":
            if c == '\\':
                i += 1
            elif c == "'":
                state = "NORMAL"

        elif state == "IN_SINGLE_COMMENT":
            if c == '\n':
                state = "NORMAL"

        elif state == "IN_MULTI_COMMENT":
            if c == '*' and nxt == '/':
                state = "NORMAL"
                i += 1

        i += 1

    if state == "IN_MULTI_COMMENT":
        errors.append("Ошибка: незакрытый многострочный комментарий")

    return errors


def remove_comments(code):
    # удаление /* ... */
    code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
    # удаление //
    code = re.sub(r'//.*', '', code)
    return code


def clean_cpp_code(source_code):
    errors = []
    info = []

    # --- 1. Валидация комментариев ---
    errors.extend(check_comments(source_code))
    if errors:
        return "", info, errors

    # --- 2. Временно убираем строки и char ---
    literals = []

    def save_literal(m):
        literals.append(m.group(0))
        return f"\x00LIT{len(literals) - 1}\x00"

    source_code = re.sub(r'"(?:[^"\\]|\\.)*"', save_literal, source_code)
    source_code = re.sub(r"'(?:[^'\\]|\\.)*'", save_literal, source_code)

    # --- 3. Удаляем комментарии ---
    removed_ml = re.findall(r'/\*.*?\*/', source_code, flags=re.DOTALL)
    if removed_ml:
        info.append(f"Информация: удалено многострочных комментариев: {len(removed_ml)}")

    source_code = re.sub(r'/\*.*?\*/', '', source_code, flags=re.DOTALL)

    removed_sl = re.findall(r'//.*', source_code)
    if removed_sl:
        info.append(f"Информация: удалено однострочных комментариев: {len(removed_sl)}")

    source_code = re.sub(r'//.*', '', source_code)

    # --- 4. Возвращаем литералы ---
    for i, lit in enumerate(literals):
        source_code = source_code.replace(f"\x00LIT{i}\x00", lit)

    # --- 5. Очистка форматирования ---
    source_code = re.sub(r'^[ \t]+|[ \t]+$', '', source_code, flags=re.MULTILINE)
    source_code = re.sub(r'\n{2,}', '\n', source_code)
    source_code = source_code.strip()

    # --- 6. Проверка недопустимых символов (строгий ASCII) ---
    invalid = re.findall(r'[^\x09\x0A\x0D\x20-\x7E]', source_code)

    if invalid:
        unique = sorted(set(f"U+{ord(c):04X}" for c in invalid))
        errors.append(
            f"Ошибка: обнаружены недопустимые символы: {', '.join(unique)}"
        )

    return source_code, info, errors


if __name__ == "__main__":
    filename = sys.argv[1] if len(sys.argv) > 1 else "test.cpp"

    try:
        with open(filename, "r", encoding="utf-8") as f:
            code = f.read()
    except FileNotFoundError:
        print(f"Ошибка: файл '{filename}' не найден.")
        sys.exit(1)
    except UnicodeDecodeError:
        print(f"Ошибка: не удалось прочитать файл '{filename}' как UTF-8.")
        sys.exit(1)

    cleaned_code, info_messages, errors = clean_cpp_code(code)

    # --- Ошибки ---
    if errors:
        print("Сообщения об ошибках:")
        for err in errors:
            print(f"  {err}")
        sys.exit(1)

    # --- Информация ---
    if info_messages:
        print("Информационные сообщения:")
        for msg in info_messages:
            print(f"  {msg}")
        print()

    # --- Результат ---
    print("Очищенный код:")
    print("-" * 60)
    print(cleaned_code)
    print("-" * 60)

    print("Ошибок не обнаружено.")