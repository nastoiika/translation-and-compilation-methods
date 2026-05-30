import sys
sys.path.insert(0, ".")

from lexer import Lexer, Token
from cleaner import clean_cpp_code

from parser3 import SyntaxAnalyzer, render_tree, SyntaxError, TreeNode

from semantic import SemanticAnalyzer, symbols_to_text, triples_to_text

KEYWORD_TO_IDENT = {"cout", "endl", "std", "namespace", "using"}
SKIP_TYPES = {"PREPROCESSOR", "ERROR"}

# Чтение и очистка кода из test.cpp через cleaner
with open("test.cpp", "r", encoding="utf-8") as f:
    SOURCE, _, errors = clean_cpp_code(f.read())

if errors:
    print("Ошибки при очистке кода:")
    for err in errors:
        print(f"  {err}")
    sys.exit(1)

print("─" * 60)
print("ПРЕПРОЦЕССИНГ (ЛР1):")
print("─" * 60)
print("✔ Препроцессинг завершён успешно. Комментарии удалены.")
print()
print("Очищенный код:")
print(SOURCE)
print()

# ─────────────────────────────────────────────
# 2. Лексический анализ (ЛР2)
# ─────────────────────────────────────────────
lexer = Lexer(SOURCE)
lex_tokens = lexer.tokenize()
lex_tokens = [t for t in lex_tokens if t.type not in SKIP_TYPES]

# 2. Конвертация типов токенов под ожидания синтаксического анализатора
def convert(t: Token) -> Token:
    token_type = t.type
    if token_type == "STRING_LITERAL":
        token_type = "CONSTANT_STRING"
    if token_type == "BOOL_CONST":
        token_type = "CONSTANT_BOOL"
    if token_type == "KEYWORD" and t.value in KEYWORD_TO_IDENT:
        token_type = "IDENTIFIER"
    return Token(token_type, t.value, t.line)

parse_tokens = [convert(t) for t in lex_tokens]

print("─" * 60)
print("ЛЕКСИЧЕСКИЙ АНАЛИЗ (ЛР2):")
print("─" * 60)
print([(t.type, t.value) for t in parse_tokens])
print()
print("✔ Лексический анализ завершён успешно. Ошибок не найдено.")
print()

# ─────────────────────────────────────────────
# 3. Синтаксический анализ (ЛР3)
# ─────────────────────────────────────────────
try:
    syntax_analyzer = SyntaxAnalyzer(parse_tokens)
    ast = syntax_analyzer.build_tree()

    print("─" * 60)
    print("СИНТАКСИЧЕСКИЙ АНАЛИЗ (ЛР3):")
    print("─" * 60)
    print(render_tree(ast))
    print()
    print("✔ Синтаксический анализ завершён успешно. Ошибок не найдено.")
    print()

except SyntaxError as e:
    print(str(e))
    print("✘ Синтаксический анализ завершён с ошибками.")
    sys.exit(1)

# ─────────────────────────────────────────────
# 4. Семантический анализ и генерация ПП (ЛР4)
# ─────────────────────────────────────────────
print("─" * 60)
print("СЕМАНТИЧЕСКИЙ АНАЛИЗ И ГЕНЕРАЦИЯ ПП (ЛР4):")
print("─" * 60)

sem_analyzer = SemanticAnalyzer()
symbols, errors, triads = sem_analyzer.analyze(ast)

print("ТАБЛИЦА СИМВОЛОВ:")
print(symbols_to_text(symbols))
print()

print("ТРИАДЫ:")
print(triples_to_text(triads))
print()

if errors:
    print("─" * 60)
    print("СЕМАНТИЧЕСКИЕ ОШИБКИ:")
    print("─" * 60)
    for idx, err in enumerate(errors, start=1):
        print(f"  {idx}. {err}")
    print()
    print("✘ Семантический анализ завершён с ошибками.")
    sys.exit(1)
else:
    print("✔ Семантический анализ завершён успешно. Ошибок не найдено.")