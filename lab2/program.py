from dataclasses import dataclass
from typing import List
 
KEYWORDS = {
    'int', 'double', 'float', 'char', 'bool', 'void', 'long', 'short',
    'unsigned', 'signed', 'const', 'static', 'return', 'if', 'else',
    'for', 'while', 'do', 'break', 'continue', 'switch', 'case',
    'default', 'true', 'false', 'nullptr', 'include', 'using',
    'namespace', 'std', 'class', 'struct', 'public', 'private',
    'protected', 'new', 'delete', 'endl', 'cout'
}
 
OPERATORS_2 = {'==', '!=', '<=', '>=', '&&', '||', '++', '--', '+=',
               '-=', '*=', '/=', '::', '<<', '>>'}
OPERATORS_1 = {'+', '-', '*', '/', '%', '=', '<', '>', '!', '&', '|',
               '^', '~'}
 
# Символы, из которых состоят операторы
OP_CHARS = set('=!<>&|+-*/%^~')
 
DELIMITERS = {';', ',', '(', ')', '{', '}', '[', ']', '.', ':'}
 
 
@dataclass
class Token:
    type: str
    value: str
    line: int
 
@dataclass
class LexError:
    line: int
    error_type: str
    detail: str
 
 
class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.tokens: List[Token] = []
        self.errors: List[LexError] = []
        self.pos = 0
        self.line = 1
 
    def current(self) -> str:
        return self.source[self.pos] if self.pos < len(self.source) else ''
 
    def peek(self, offset=1) -> str:
        i = self.pos + offset
        return self.source[i] if i < len(self.source) else ''
 
    def advance(self) -> str:
        ch = self.source[self.pos]
        if ch == '\n':
            self.line += 1
        self.pos += 1
        return ch
 
    def skip_whitespace(self):
        while self.pos < len(self.source) and self.current() in ' \t\r\n':
            self.advance()
 
    def read_number(self) -> Token:
        start_line = self.line
        num = ''
        dot_count = 0
        has_letter_error = False
 
        while self.pos < len(self.source):
            ch = self.current()
            if ch.isdigit():
                num += self.advance()
            elif ch == '.':
                dot_count += 1
                num += self.advance()
                if dot_count > 1:
                    self.errors.append(LexError(
                        line=start_line,
                        error_type='INVALID_NUMBER',
                        detail=f'Две точки подряд в числе: «{num}»'
                    ))
            elif ch.isalpha() or ch == '_':
                has_letter_error = True
                num += self.advance()
            else:
                break
 
        if has_letter_error:
            self.errors.append(LexError(
                line=start_line,
                error_type='INVALID_NUMBER',
                detail=f'Буквы в числовой константе: «{num}»'
            ))
            return Token('ERROR', num, start_line)
 
        if dot_count == 0:
            return Token('CONSTANT_INT', num, start_line)
        elif dot_count == 1:
            return Token('CONSTANT_FLOAT', num, start_line)
        else:
            return Token('ERROR', num, start_line)
 
    def read_identifier(self) -> Token:
        start_line = self.line
        word = ''
        # Читаем все символы, которые могут быть частью слова,
        # включая не-ASCII (чтобы поймать их как ошибку, а не бросить посреди токена)
        while self.pos < len(self.source):
            ch = self.current()
            if ch.isalnum() or ch == '_' or ord(ch) > 127:
                word += self.advance()
            else:
                break
 
        # ── Категории (определены заранее) ──────────────────────────────
        # KEYWORD     : слово ровно совпадает с элементом таблицы ключевых слов
        # BOOL_CONST  : true / false
        # IDENTIFIER  : matches [a-zA-Z_][a-zA-Z0-9_]*  (только ASCII)
        # Всё остальное — ОШИБКА.
 
        import re
        VALID_IDENTIFIER = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')
 
        if word in ('true', 'false'):
            return Token('BOOL_CONST', word, start_line)
 
        if word in KEYWORDS:
            return Token('KEYWORD', word, start_line)
 
        if VALID_IDENTIFIER.match(word):
            return Token('IDENTIFIER', word, start_line)
 
        # Слово не попало ни в одну категорию — лексическая ошибка
        bad_chars = ''.join(dict.fromkeys(c for c in word if ord(c) > 127 or not (c.isalnum() or c == '_')))
        self.errors.append(LexError(
            line=start_line,
            error_type='INVALID_TOKEN',
            detail=(f'«{word}» не является ключевым словом, идентификатором или константой. '
                    f'Недопустимые символы: «{bad_chars}»' if bad_chars else
                    f'«{word}» не соответствует ни одной допустимой категории лексем.')
        ))
        return Token('ERROR', word, start_line)
 
    def read_string(self) -> Token:
        start_line = self.line
        quote = self.advance()
        s = quote
        closed = False
        while self.pos < len(self.source):
            ch = self.current()
            if ch == '\n':
                break
            s += self.advance()
            if ch == quote:
                closed = True
                break
        if not closed:
            self.errors.append(LexError(
                line=start_line,
                error_type='UNCLOSED_STRING',
                detail=f'Незакрытый строковый литерал: {s}'
            ))
            return Token('ERROR', s, start_line)
        return Token('STRING_LITERAL', s, start_line)
 
    def read_preprocessor(self) -> Token:
        start_line = self.line
        s = ''
        while self.pos < len(self.source) and self.current() != '\n':
            s += self.advance()
        return Token('PREPROCESSOR', s, start_line)
 
    # Легальные комбинации из 2+ операторов подряд без пробела (C++ допускает)
    VALID_COMBINATIONS = {
        # i++ ) или --i и похожее — читается как два отдельных токена, не ошибка
        # Перечисляем то, что НЕ является ошибкой при длине raw > 2:
        # на самом деле мы не запрещаем комбинации вида ++ или --, они уже в OPERATORS_2.
        # Запрещаем только сырые последовательности длиннее 2 символов.
    }
 
    def read_operator(self) -> Token:
        start_line = self.line
 
        # Жадно читаем всю последовательность операторных символов
        raw = ''
        while self.pos < len(self.source) and self.current() in OP_CHARS:
            raw += self.advance()
 
        # Если raw — ровно один известный оператор, всё хорошо
        if raw in OPERATORS_2:
            return Token('OPERATOR', raw, start_line)
        if raw in OPERATORS_1:
            return Token('OPERATOR', raw, start_line)
 
        # Если длина > 2 — любая такая последовательность подозрительна.
        # Пытаемся угадать, что имел в виду программист: ищем самый длинный
        # известный оператор, с которого начинается raw.
        if len(raw) > 2:
            hint = None
            if raw[:2] in OPERATORS_2:
                hint = raw[:2]
            elif raw[:1] in OPERATORS_1:
                hint = raw[:1]
            hint_str = f' — возможно, имелось в виду «{hint}»' if hint else ''
            self.errors.append(LexError(
                line=start_line,
                error_type='UNKNOWN_OPERATOR',
                detail=f'Недопустимая последовательность операторов: «{raw}»{hint_str}'
            ))
            return Token('ERROR', raw, start_line)
 
        # Длина 1 или 2, но не в таблицах — неизвестный символ
        self.errors.append(LexError(
            line=start_line,
            error_type='UNKNOWN_SYMBOL',
            detail=f'Недопустимый символ или оператор: «{raw}»'
        ))
        return Token('ERROR', raw, start_line)
 
    # Типы данных — после них ожидается идентификатор, не оператор
    TYPE_KEYWORDS = {
        'int', 'double', 'float', 'char', 'bool', 'void',
        'long', 'short', 'unsigned', 'signed'
    }
 
    def tokenize(self) -> List[Token]:
        while self.pos < len(self.source):
            self.skip_whitespace()
            if self.pos >= len(self.source):
                break
 
            ch = self.current()
            start_line = self.line
 
            if ch == '#':
                self.tokens.append(self.read_preprocessor())
            elif ch.isdigit():
                self.tokens.append(self.read_number())
            elif ch.isalpha() or ch == '_':
                self.tokens.append(self.read_identifier())
            elif ch in ('"', "'"):
                self.tokens.append(self.read_string())
            elif ch in DELIMITERS:
                self.tokens.append(Token('DELIMITER', self.advance(), start_line))
            elif ch in OP_CHARS:
                self.tokens.append(self.read_operator())
            else:
                self.errors.append(LexError(
                    line=start_line,
                    error_type='UNKNOWN_SYMBOL',
                    detail=f'Недопустимый символ: «{ch}»'
                ))
                self.tokens.append(Token('ERROR', self.advance(), start_line))
 
        self._check_invalid_identifiers()
        return self.tokens
 
    def _check_invalid_identifiers(self):
        """
        Постобработка: ищем паттерн  TYPE  OPERATOR(ы)  IDENTIFIER
        Пример: double !!x = 10  →  !!x — недопустимое имя переменной.
        Также ловим OPERATOR прямо склеенный с идентификатором без пробела
        когда предыдущий токен — тип данных.
        """
        toks = self.tokens
        i = 0
        while i < len(toks):
            tok = toks[i]
            # Паттерн: тип → один или несколько OPERATOR/ERROR → IDENTIFIER
            if tok.type == 'KEYWORD' and tok.value in self.TYPE_KEYWORDS:
                j = i + 1
                op_tokens = []
                # Собираем все операторы/ошибки подряд
                while j < len(toks) and toks[j].type in ('OPERATOR', 'ERROR'):
                    op_tokens.append(toks[j])
                    j += 1
                # Если после операторов идёт идентификатор — это ошибка
                if op_tokens and j < len(toks) and toks[j].type in ('IDENTIFIER', 'KEYWORD'):
                    bad_prefix = ''.join(t.value for t in op_tokens)
                    ident = toks[j].value
                    bad_name = bad_prefix + ident
                    line = op_tokens[0].line
                    self.errors.append(LexError(
                        line=line,
                        error_type='INVALID_IDENTIFIER',
                        detail=(f'Идентификатор «{bad_name}» начинается со спецсимволов «{bad_prefix}» — '                                f'имя переменной должно начинаться с буквы или _')
                    ))
                    # Помечаем все операторы-префиксы как ERROR
                    for ot in op_tokens:
                        ot.type = 'ERROR'
            i += 1
 
 
def print_table(tokens: List[Token]):
    print(f"\n{'Лексема':<30} | {'Тип':<20} | {'Строка'}")
    print('-' * 65)
    for t in tokens:
        print(f"{t.value:<30} | {t.type:<20} | {t.line}")
 
def print_sequence(tokens: List[Token]):
    seq = [(t.type, t.value) for t in tokens]
    print('\nПоследовательность лексем:')
    print(seq)
 
def print_errors(errors: List[LexError]):
    if errors:
        print(f'\n⚠  Обнаружено ошибок: {len(errors)}')
        for e in errors:
            print(f'  Строка {e.line} | {e.error_type}: {e.detail}')
    else:
        print('\n✓  Лексических ошибок не обнаружено.')
 
def print_summary(tokens: List[Token], errors: List[LexError]):
    ok = all(t.type != 'ERROR' for t in tokens)
    status = 'успешно' if ok else 'с ошибками'
    print(f'\nЛексический анализ завершён {status}. '
          f'Обнаружено {len(tokens)} токенов. '
          f'Ошибок: {len(errors)}.')
 


import sys
if __name__ == '__main__':
    filename = sys.argv[1] if len(sys.argv) > 1 else "test.cpp"

    try:
        with open(filename, "r", encoding="utf-8") as f:
            source = f.read()
    except FileNotFoundError:
        print(f"Ошибка: файл '{filename}' не найден.")
        sys.exit(1)
    except UnicodeDecodeError:
        print(f"Ошибка: не удалось прочитать файл '{filename}' как UTF-8.")
        sys.exit(1)

    lexer = Lexer(source)
    tokens = lexer.tokenize()
 
    print_table(tokens)
    print_sequence(tokens)
    print_errors(lexer.errors)
    print_summary(tokens, lexer.errors)