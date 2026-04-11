import re
import sys

from pyparsing import line

#  Таблицы лексем (только конструкции test.py)
KEYWORDS = {
    "def", "return", "if", "elif", "else",
    "for", "while", "in", "not", "and", "or",
    "import", "from", "class", "pass", "break",
    "continue", "None", "True", "False",
}

BOOL_CONSTANTS = {"True", "False"}

# Операторы — от длинных к коротким, чтобы // не распался на / /
OPERATORS = [
    "//", "**", "+=", "-=", "*=", "/=", "%=",
    "**=", "//=", "==", "!=", "<=", ">=",
    "=", "+", "-", "*", "/", "%", "<", ">",
]

DELIMITERS = set("()[]{}:.,;")


#  Вспомогательные паттерны
RE_FLOAT   = re.compile(r'\d+\.\d*([eE][+-]?\d+)?|\d+[eE][+-]?\d+|\.\d+([eE][+-]?\d+)?')
RE_INT_HEX = re.compile(r'0[xX][0-9a-fA-F_]+')
RE_INT_OCT = re.compile(r'0[oO][0-7_]+')
RE_INT_BIN = re.compile(r'0[bB][01_]+')
RE_INT_DEC = re.compile(r'\d[\d_]*')
RE_IDENT   = re.compile(r'[A-Za-z_]\w*')
RE_NEWLINE = re.compile(r'\n')
RE_INDENT  = re.compile(r'[ \t]+')
RE_COMMENT = re.compile(r'#[^\n]*')



#  Токен
class Token:
    def __init__(self, ttype, value, line):
        self.ttype = ttype   # строковое имя типа
        self.value = value
        self.line  = line

    def __repr__(self):
        return f"({self.ttype}, {self.value!r})"


#  Лексический анализатор
def tokenize(source: str):
    tokens = []
    errors = []
    pos    = 0
    line   = 1
    n      = len(source)

    while pos < n:
        # --- пропустить комментарий
        m = RE_COMMENT.match(source, pos)
        if m:
            pos = m.end()
            continue

        # --- перевод строки
        if source[pos] == '\n':
            line += 1
            pos  += 1
            continue

        # --- пробелы / табы
        if source[pos] in ' \t\r':
            pos += 1
            continue

        # --- строковый литерал (тройные и одинарные)
        if source[pos] in ('"', "'"):
            q = source[pos]
            # тройные кавычки?
            if source[pos:pos+3] in ('"""', "'''"):
                q3   = source[pos:pos+3]
                end  = source.find(q3, pos + 3)
                if end == -1:
                    errors.append(f"Строка {line}: незакрытый строковый литерал (тройные кавычки)")
                    pos = n
                else:
                    val = source[pos:end+3]
                    tokens.append(Token("CONSTANT_STR", val, line))
                    line += val.count('\n')
                    pos   = end + 3
            else:
                # одинарные / двойные
                i = pos + 1
                buf = q
                ok  = False
                while i < n:
                    c = source[i]
                    if c == '\n':
                        break
                    buf += c
                    if c == '\\' and i + 1 < n:
                        i += 1
                        buf += source[i]
                    elif c == q:
                        ok = True
                        i += 1
                        break
                    i += 1
                if not ok:
                    errors.append(f"Строка {line}: незакрытый строковый литерал")
                    pos = i
                else:
                    tokens.append(Token("CONSTANT_STR", buf, line))
                    pos = i
            continue

        # --- ошибка: две точки подряд в числе (12..3)
        if source[pos].isdigit():
            m_num = re.match(r'\d+', source[pos:])
            if m_num:
                end_num = pos + len(m_num.group())
                if end_num + 1 < n and source[end_num:end_num+2] == "..":
                    errors.append(
                        f"Строка {line}: некорректная вещественная константа (две точки подряд)"
                    )
                    pos = end_num + 2
                    continue

        # --- вещественная константа (проверяем РАНЬШЕ целой)
        m = RE_FLOAT.match(source, pos)
        if m:
            val = m.group()
            # проверка «две точки подряд» не нужна — RE_FLOAT не пропустит
            tokens.append(Token("CONSTANT_FLOAT", val, line))
            pos = m.end()
            continue

        # --- целая константа (hex / oct / bin / dec)
        m = (RE_INT_HEX.match(source, pos) or
             RE_INT_OCT.match(source, pos) or
             RE_INT_BIN.match(source, pos))
        if m:
            val = m.group()
            tokens.append(Token("CONSTANT_INT", val, line))
            pos = m.end()
            continue

        m = RE_INT_DEC.match(source, pos)
        if m:
            val = m.group()
            # следующий символ — буква? → ошибка (типа 123abc)
            if pos + len(val) < n and (source[pos+len(val)].isalpha() or source[pos+len(val)] == '_'):
                errors.append(f"Строка {line}: некорректный числовой литерал «{val}{source[pos+len(val)]}...»")
                pos = m.end()
                while pos < n and (source[pos].isalnum() or source[pos] == '_'):
                    pos += 1
            else:
                tokens.append(Token("CONSTANT_INT", val, line))
                pos = m.end()
            continue

        # --- ошибка: идентификатор начинается с цифры (например 1abc)
        m = re.match(r'\d+[A-Za-z_]\w*', source[pos:])
        if m:
            errors.append(
                f"Строка {line}: идентификатор не может начинаться с цифры «{m.group()}»"
            )
            pos += len(m.group())
            continue

        # --- идентификатор / ключевое слово / булева константа
        m = RE_IDENT.match(source, pos)
        if m:
            val = m.group()
            if val in BOOL_CONSTANTS:
                ttype = "CONSTANT_BOOL"
            elif val in KEYWORDS:
                ttype = "KEYWORD"
            else:
                ttype = "IDENTIFIER"
            tokens.append(Token(ttype, val, line))
            pos = m.end()
            continue

        # --- оператор (длинные первыми)
        matched_op = None
        for op in OPERATORS:
            if source[pos:pos+len(op)] == op:
                matched_op = op
                break

        if matched_op:
            tokens.append(Token("OPERATOR", matched_op, line))
            pos += len(matched_op)
            continue


        # --- возможный неизвестный оператор
        if source[pos] in "+-*/=%!<>^&|":
            errors.append(
                f"Строка {line}: неизвестный оператор «{source[pos]}»"
            )
            pos += 1
            continue


        # --- разделитель
        if source[pos] in DELIMITERS:
            tokens.append(Token("DELIMITER", source[pos], line))
            pos += 1
            continue


        # --- недопустимый символ
        errors.append(
            f"Строка {line}: недопустимый символ «{source[pos]}»"
        )
        pos += 1

    return tokens, errors


#  Печать таблиц лексем
TYPE_LABELS = {
    "KEYWORD":        "Ключевые слова",
    "IDENTIFIER":     "Идентификаторы",
    "CONSTANT_INT":   "Целочисленные константы",
    "CONSTANT_FLOAT": "Вещественные константы",
    "CONSTANT_STR":   "Строковые константы",
    "CONSTANT_BOOL":  "Булевы константы",
    "OPERATOR":       "Операторы",
    "DELIMITER":      "Разделители",
}

TYPE_ORDER = list(TYPE_LABELS.keys())


def print_tables(tokens):
    from collections import defaultdict, OrderedDict

    # собираем уникальные лексемы по типу (сохраняем порядок первого вхождения)
    seen   = defaultdict(list)
    seen_v = defaultdict(set)
    for tok in tokens:
        if tok.value not in seen_v[tok.ttype]:
            seen[tok.ttype].append(tok.value)
            seen_v[tok.ttype].add(tok.value)

    print("\n" + "═" * 60)
    print("  ТАБЛИЦЫ ЛЕКСЕМ")
    print("═" * 60)

    for idx, ttype in enumerate(TYPE_ORDER, 1):
        label  = TYPE_LABELS[ttype]
        values = seen.get(ttype, [])
        if not values:
            continue
        print(f"\nТаблица {idx} – {label}")
        print(f"{'id':<5} {'Лексема':<20} {'Тип'}")
        print("-" * 45)
        for i, v in enumerate(values, 1):
            print(f"{i:<5} {v:<20} {ttype}")


def print_token_sequence(tokens):
    print("\n" + "═" * 60)
    print("  ПОСЛЕДОВАТЕЛЬНОСТЬ ЛЕКСЕМ (таблица разбора)")
    print("═" * 60)
    print(f"{'Лексема':<22} {'Тип'}")
    print("-" * 45)
    for tok in tokens:
        print(f"{tok.value:<22} {tok.ttype}")

    print("\nСписок объектов для синтаксического анализатора:")
    print("[", end="")
    print(", ".join(str(t) for t in tokens), end="")
    print("]")


#  Точка входа
def main():
    # Тестовая программа (содержимое test.py)
    with open("test.py", "r", encoding="utf-8") as f:
        source = f.read()

    print("Исходный код (test.py):")
    print("─" * 45)
    print(source)

    tokens, errors = tokenize(source)

    # Таблицы лексем
    print_tables(tokens)

    # Полная последовательность
    print_token_sequence(tokens)

    # Итог
    print("\n" + "═" * 60)
    if errors:
        print(f"  Обнаружено ошибок: {len(errors)}")
        for e in errors:
            print(f"{e}")
    else:
        print(f"  Лексический анализ завершён успешно.")
    print(f"  Обнаружено токенов: {len(tokens)}")
    print("═" * 60)


if __name__ == "__main__":
    main()