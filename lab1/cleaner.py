import re
import sys


def clean_cpp_code(source_code):
    errors = []
    info = []

    # --- Проверка незакрытого многострочного комментария /* ... */ ---
    # Считаем вхождения /* и */
    open_count = len(re.findall(r'/\*', source_code))
    close_count = len(re.findall(r'\*/', source_code))
    if open_count != close_count:
        errors.append(
            f"Ошибка: незакрытый многострочный комментарий "
            f"(найдено '/*': {open_count}, '*/': {close_count})"
        )

    # --- Удалить строковые и символьные литералы временно,
    #     чтобы не трогать // и /* внутри строк ---
    # Заменяем их заглушками, потом вернём
    literals = []

    def save_literal(m):
        literals.append(m.group(0))
        return f"\x00LIT{len(literals) - 1}\x00"

    # Строковые литералы "..."  (с учётом экранирования)
    source_code = re.sub(r'"(?:[^"\\]|\\.)*"', save_literal, source_code)
    # Символьные литералы '.'
    source_code = re.sub(r"'(?:[^'\\]|\\.)*'", save_literal, source_code)

    # --- Удалить многострочные комментарии /* ... */ ---
    removed_ml = re.findall(r'/\*.*?\*/', source_code, flags=re.DOTALL)
    if removed_ml:
        info.append(f"Информация: удалено многострочных комментариев: {len(removed_ml)}")
    source_code = re.sub(r'/\*.*?\*/', '', source_code, flags=re.DOTALL)

    # --- Удалить однострочные комментарии // ---
    removed_sl = re.findall(r'//.*', source_code)
    if removed_sl:
        info.append(f"Информация: удалено однострочных комментариев: {len(removed_sl)}")
    source_code = re.sub(r'//.*', '', source_code)

    # --- Вернуть строковые литералы ---
    for i, lit in enumerate(literals):
        source_code = source_code.replace(f"\x00LIT{i}\x00", lit)

    # --- Удалить пробелы/табы в начале и конце строк ---
    source_code = re.sub(r'^[ \t]+|[ \t]+$', '', source_code, flags=re.MULTILINE)

    # --- Удалить пустые строки ---
    source_code = re.sub(r'\n{2,}', '\n', source_code)
    source_code = source_code.strip()

    # --- Проверка недопустимых символов (управляющие, кроме \t \n \r) ---
    invalid = re.findall(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', source_code)
    if invalid:
        unique = sorted(set(f"\\x{ord(c):02X}" for c in invalid))
        errors.append(
            f"Ошибка: обнаружены недопустимые управляющие символы: {', '.join(unique)}"
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

    # --- Вывод информационных сообщений ---
    if info_messages:
        print("Информационные сообщения:")
        for msg in info_messages:
            print(f"  {msg}")
        print()

    # --- Вывод ошибок ---
    if errors:
        print("Сообщения об ошибках:")
        for err in errors:
            print(f"  {err}")
        print()

    # --- Вывод очищенного кода ---
    print("Очищенный код:")
    print("-" * 60)
    print(cleaned_code)
    print("-" * 60)

    if not errors:
        print("Ошибок не обнаружено.")
    else:
        print("Обнаружены ошибки. Смотрите сообщения выше.")