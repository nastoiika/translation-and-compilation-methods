import sys
sys.path.insert(0, ".")

from lexer import Lexer, Token

sys.path.insert(0, "./3")
from parser3 import SyntaxAnalyzer, render_tree, SyntaxError, TreeNode

KEYWORD_TO_IDENT = {"cout", "endl", "std", "namespace", "using"}
SKIP_TYPES = {"PREPROCESSOR", "ERROR"}

SOURCE = """
double add(double a, double b) {
    double result = a + b;
    return result;
}
double mult(double a, double b) {
    double result = a * b;
    return result;
}
int main() {
    double x = 10;
    double y = 20;
    double z = x * 2 + y / 5;
    double q = (x + y) * 3;
    if (z > 15 && x < y) {
        std::cout << "Condition true" << std::endl;
    } else {
        std::cout << "Condition false" << std::endl;
    }
    if (q > z) {
        std::cout << "Condition true" << std::endl;
    } else {
        std::cout << "Condition false" << std::endl;
    }
    for (int i = 0; i < 3; i++) {
        std::cout << add(i, z) << std::endl;
    }
    for (int i = 0; i < 5; i++) {
        std::cout << mult(i, q) << std::endl;
    }
    return 0;
}
"""

# 1. Лексический анализ (ЛР2)
lexer = Lexer(SOURCE)
lex_tokens = lexer.tokenize()
lex_tokens = [t for t in lex_tokens if t.type not in SKIP_TYPES]

# 2. Конвертация типов токенов под ожидания анализатора
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

# 3. Вывод входного потока токенов
print("─" * 60)
print("ВХОДНОЙ ПОТОК ТОКЕНОВ (ЛР2):")
print("─" * 60)
print([(t.type, t.value) for t in parse_tokens])
print()

# 4. Синтаксический анализ (ЛР3)
try:
    analyzer = SyntaxAnalyzer(parse_tokens)
    ast = analyzer.build_tree()

    print("─" * 60)
    print("АБСТРАКТНОЕ СИНТАКСИЧЕСКОЕ ДЕРЕВО:")
    print("─" * 60)
    print(render_tree(ast))
    print()
    print("Синтаксический анализ завершён успешно. Ошибок не найдено.")

except SyntaxError as e:
    print(str(e))
    print("Синтаксический анализ завершён с ошибками.")