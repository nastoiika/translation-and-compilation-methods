from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lexer import Token


PRIMITIVE_TYPES = {"int", "double", "bool", "char", "long"}

DECL_STARTERS = {
    "int",
    "double",
    "bool",
    "char",
    "long",
    "const",
}

ASSIGN_OPS = {
    "=",
    "+=",
    "*=",
    "-=",
    "/=",
    "%=",
}

OP_PRIORITY = {
    "||": 1,
    "&&": 2,
    "==": 3,
    "!=": 3,
    "<":  4,
    "<=": 4,
    ">":  4,
    "<<": 5,
    "+":  6,
    "-":  6,
    "*":  7,
    "/":  7,
    "%":  7,
}


@dataclass
class TreeNode:
    tag: str
    data: Dict[str, Any] = field(default_factory=dict)

    def serialize(self) -> Dict[str, Any]:
        def _conv(val: Any) -> Any:
            if isinstance(val, TreeNode):
                return val.serialize()
            if isinstance(val, list):
                return [_conv(v) for v in val]
            return val

        return {
            "tag": self.tag,
            **{k: _conv(v) for k, v in self.data.items()},
        }


@dataclass
class SyntaxError(Exception):
    msg: str
    row: int
    col: int
    expected: str
    got: str

    def __str__(self) -> str:
        pos_info = (
            f"строка {self.row}, столбец {self.col}"
            if self.row
            else "позиция неизвестна"
        )
        return (
            f"[СИНТАКСИЧЕСКАЯ ОШИБКА] {self.msg}\n"
            f"  Позиция  : {pos_info}\n"
            f"  Ожидалось: {self.expected}\n"
            f"  Получено : {self.got}"
        )


class SyntaxAnalyzer:
    def __init__(self, token_stream: List[Token]) -> None:
        self.stream = token_stream
        self.idx = 0

    # ---------- Навигация по потоку ----------

    def cur(self) -> Optional[Token]: #Возвращает текущий токен по индексу idx, или None если токены кончились
        if self.idx >= len(self.stream):
            return None
        return self.stream[self.idx]

    def look_ahead(self, offset: int = 1) -> Optional[Token]: #Смотрит на токен впереди не сдвигая idx
        pos = self.idx + offset
        if pos >= len(self.stream):
            return None
        return self.stream[pos]

    def finished(self) -> bool: #Проверяет закончились ли токены
        return self.idx >= len(self.stream)

    def _tok_str(self, token: Optional[Token]) -> str: #Преобразует токен в строку для отображения в ошибках
        if token is None:
            return "конец потока"
        return f"({token.type}, {token.value!r})"

    def _make_error(self, msg: str, expected: str) -> SyntaxError: #Создаёт объект SyntaxError с информацией о текущем токене и ожидаемом
        current_token = self.cur()
        if current_token is None:
            return SyntaxError(msg, 0, 0, expected, "конец потока")
        return SyntaxError(msg, current_token.line, current_token.column, expected, self._tok_str(current_token))

    def _try_consume( #Пытается потребить токен, если он соответствует ожидаемому типу и/или значению. Если совпало, сдвигает idx и возвращает токен, иначе возвращает None
        self,
        expected_type: Optional[str] = None,
        expected_value: Optional[str] = None,
    ) -> Optional[Token]:
        current_token = self.cur()
        if current_token is None:
            return None
        if expected_type is not None and current_token.type != expected_type:
            return None
        if expected_value is not None and current_token.value != expected_value:
            return None
        self.idx += 1
        return current_token

    def _peek_check(#Проверяет, соответствует ли текущий токен ожидаемому типу и/или значению, не сдвигая idx
        self,
        expected_type: Optional[str] = None,
        expected_value: Optional[str] = None,
    ) -> bool:
        current_token = self.cur()
        if current_token is None:
            return False
        if expected_type is not None and current_token.type != expected_type:
            return False
        if expected_value is not None and current_token.value != expected_value:
            return False
        return True

    def _require( #Потребляет токен, если он соответствует ожидаемому типу и/или значению, иначе выбрасывает SyntaxError с помощью _make_error
        self,
        expected_type: str,
        expected_value: Optional[str] = None,
        hint: Optional[str] = None,
    ) -> Token:
        consumed_token = self._try_consume(expected_type, expected_value)
        if consumed_token is None:
            label = hint or (f"{expected_type} {expected_value!r}" if expected_value is not None else expected_type)
            raise self._make_error("нарушена структура программы", label)
        return consumed_token

    def _check_val(self, expected_value: str) -> bool: #Проверяет, что текущий токен имеет конкретное значение expected_value, не сдвигая idx
        current_token = self.cur()
        return current_token is not None and current_token.value == expected_value

    def _require_val(self, expected_value: str, hint: Optional[str] = None) -> Token: #Потребляет токен, если он имеет конкретное значение expected_value, иначе выбрасывает SyntaxError
        current_token = self.cur()
        if current_token is None or current_token.value != expected_value:
            raise self._make_error("отсутствует обязательная лексема", hint or expected_value)
        self.idx += 1
        return current_token

    # ---------- Разбор верхнего уровня ----------

    def build_tree(self) -> TreeNode: #Точка входа для синтаксического анализа. Разбирает весь поток токенов, ожидая функции, и возвращает корневой узел Program с этими функциями
        func_list: List[TreeNode] = []
        while not self.finished():
            func_list.append(self._parse_func())
        return TreeNode("Program", {"functions": func_list})

    def _parse_func(self) -> TreeNode: #Разбирает объявление функции. Ожидает тип возвращаемого значения, имя функции, список параметров в скобках и тело функции в виде блока. Возвращает узел Func с этими данными
        ret_type = self._parse_type_node()
        func_name = self._require("IDENTIFIER", hint="имя функции").value
        self._require_val("(", "открывающая скобка '(' списка параметров")
        param_list = self._parse_params()
        self._require_val(")", "закрывающая скобка ')' списка параметров")
        func_body = self._parse_compound()
        return TreeNode(
            "Func",
            {
                "ret_type": ret_type,
                "func_name": func_name,
                "params": param_list,
                "body": func_body,
            },
        )

    def _parse_params(self) -> List[TreeNode]: 
        #Разбирает список параметров функции через запятую. 
        # Каждый параметр состоит из типа и имени. Если сразу стоит закрывающая скобка, возвращает пустой список. 
        # Иначе, пока есть параметры, разбирает тип и имя каждого параметра и добавляет их в результат в виде узлов Param
        result: List[TreeNode] = []
        if self._check_val(")"):
            return result
        while True:
            param_type = self._parse_type_node()
            param_name = self._require("IDENTIFIER", hint="имя параметра").value
            result.append(TreeNode("Param", {"param_type": param_type, "param_name": param_name}))
            if not self._try_consume("DELIMITER", ","):
                break
        return result

    def _parse_type_node(self) -> TreeNode: #Разбирает тип данных: int, double, const, std::vector<T> и т.д.

        is_const = bool(self._try_consume("KEYWORD", "const"))
        base_name = ""
        tmpl_args: List[TreeNode] = []

        if self._try_consume("KEYWORD", "long"):
            base_name = "long long" if self._try_consume("KEYWORD", "long") else "long"

        elif self._peek_check("KEYWORD") and self.cur().value in {"int", "double", "bool", "char"}:
            base_name = self.cur().value
            self.idx += 1

        elif (
            self._peek_check("IDENTIFIER", "std")
            and self.look_ahead() is not None
            and self.look_ahead().value == "::"
        ):
            self._require("IDENTIFIER", "std")
            self._require("OPERATOR", "::", "оператор '::'")
            tname = self._require("IDENTIFIER", hint="имя типа std").value
            base_name = f"std::{tname}"
            if self._try_consume("OPERATOR", "<"):
                tmpl_args.append(self._parse_type_node())
                self._require("OPERATOR", ">", "закрывающая '>' шаблона")
        else:
            raise self._make_error(
                "ожидался тип данных",
                "int, double, bool, char, long, const, std::vector<T>& или std::string",
            )

        is_ref = bool(self._try_consume("OPERATOR", "&"))

        display = base_name
        if tmpl_args:
            display += "<" + ", ".join(a.data["type_name"] for a in tmpl_args) + ">"
        if is_const:
            display = "const " + display
        if is_ref:
            display += "&"

        return TreeNode(
            "TypeNode",
            {
                "type_name": display,
                "base_type": base_name,
                "is_const": is_const,
                "is_ref": is_ref,
                "tmpl_args": tmpl_args,
            },
        )

    # ---------- Операторы ----------

    def _parse_compound(self) -> TreeNode: #Разбирает блок операторов, который начинается с '{' и заканчивается '}'. 
        self._require_val("{", "открывающая фигурная скобка '{'") #Возвращает узел Block с списком операторов в виде дочерних узлов
        stmts: List[TreeNode] = []
        while not self._check_val("}"):
            if self.finished():
                raise self._make_error("незакрытый блок", "закрывающая '}'")
            stmts.append(self._parse_stmt())
        self._require_val("}", "закрывающая фигурная скобка '}'")
        return TreeNode("Block", {"stmts": stmts})

    def _parse_stmt(self) -> TreeNode: #Разбирает оператор.Если токен не соответствует ни одному из ожидаемых вариантов, выбрасывает SyntaxError
        tok = self.cur()
        if tok is None:
            raise self._make_error("ожидался оператор", "оператор или '}'")

        if tok.value == "{":
            return self._parse_compound()
        if tok.type == "KEYWORD" and tok.value == "if":
            return self._parse_if()
        if tok.type == "KEYWORD" and tok.value == "for":
            return self._parse_for()
        if tok.type == "KEYWORD" and tok.value == "while":
            return self._parse_while()
        if tok.type == "KEYWORD" and tok.value == "return":
            return self._parse_return()
        if self._is_decl():
            return self._parse_var_decl(semicolon=True)

        expr_node = self._parse_expr()
        self._require_val(";", "точка с запятой ';' после выражения")
        return TreeNode("ExprStmt", {"expr": expr_node})

    def _parse_if(self) -> TreeNode: #Разбирает оператор if. Ожидает ключевое слово "if", затем условие в скобках и тело then в виде оператора. Опционально может быть блок else с телом else в виде оператора. Возвращает узел If с этими данными
        self._require("KEYWORD", "if")
        self._require_val("(", "открывающая скобка условия if")
        condition = self._parse_expr()
        self._require_val(")", "закрывающая скобка условия if")
        then_branch = self._parse_stmt()
        else_branch = None
        if self._try_consume("KEYWORD", "else"):
            else_branch = self._parse_stmt()
        return TreeNode("If", {"cond": condition, "then_branch": then_branch, "else_branch": else_branch})

    def _parse_for(self) -> TreeNode:
        self._require("KEYWORD", "for")
        self._require_val("(", "открывающая скобка заголовка for")

        if self._is_decl():
            var_type = self._parse_type_node()
            var_name = self._require("IDENTIFIER", hint="имя переменной цикла").value

            if self._try_consume("DELIMITER", ":"):
                iterable_expression = self._parse_expr()
                self._require_val(")", "закрывающая скобка range-for")
                loop_body = self._parse_stmt()
                return TreeNode(
                    "RangeFor",
                    {
                        "loop_var": TreeNode("VarDecl", {"var_type": var_type, "var_name": var_name, "init_val": None}),
                        "iterable": iterable_expression,
                        "loop_body": loop_body,
                    },
                )

            initial_value = None
            if self._try_consume("OPERATOR", "="):
                initial_value = self._parse_expr()
            init_node = TreeNode("VarDecl", {"var_type": var_type, "var_name": var_name, "init_val": initial_value})
        elif not self._check_val(";"):
            init_node = self._parse_expr()
        else:
            init_node = None

        self._require_val(";", "точка с запятой после инициализации for")
        cond_node = None if self._check_val(";") else self._parse_expr()
        self._require_val(";", "точка с запятой после условия for")
        step_node = None if self._check_val(")") else self._parse_expr()
        self._require_val(")", "закрывающая скобка заголовка for")
        loop_body = self._parse_stmt()

        return TreeNode(
            "For",
            {"init_node": init_node, "cond_node": cond_node, "step_node": step_node, "loop_body": loop_body},
        )

    def _parse_while(self) -> TreeNode:
        self._require("KEYWORD", "while")
        self._require_val("(", "открывающая скобка условия while")
        condition = self._parse_expr()
        self._require_val(")", "закрывающая скобка условия while")
        loop_body = self._parse_stmt()
        return TreeNode("While", {"cond": condition, "loop_body": loop_body})

    def _parse_return(self) -> TreeNode:
        self._require("KEYWORD", "return")
        return_value = None if self._check_val(";") else self._parse_expr()
        self._require_val(";", "точка с запятой после return")
        return TreeNode("Return", {"ret_val": return_value})

    def _parse_var_decl(self, semicolon: bool) -> TreeNode: #`Разбирает объявление переменной. Ожидает тип, имя переменной и опционально инициализацию через '='. Если semicolon=True, требует точку с запятой в конце. Возвращает узел Var, который содержит список объявлений (хотя в данном синтаксисе всегда будет один элемент) в виде узлов VarDecl
        var_type = self._parse_type_node()
        var_name = self._require("IDENTIFIER", hint="имя переменной").value
        initial_value = None
        if self._try_consume("OPERATOR", "="):
            initial_value = self._parse_expr()
        node = TreeNode(
            "Var",
            {"decls": [TreeNode("VarDecl", {"var_type": var_type, "var_name": var_name, "init_val": initial_value})]},
        )
        if semicolon:
            self._require_val(";", "точка с запятой после объявления переменной")
        return node

    def _is_decl(self) -> bool: 
        current_token = self.cur()
        if current_token is None:
            return False
        if current_token.type == "KEYWORD" and current_token.value in DECL_STARTERS:
            return True
        if (
            current_token.type == "IDENTIFIER"
            and current_token.value == "std"
            and self.look_ahead() is not None
            and self.look_ahead().value == "::"
        ):
            third = self.look_ahead(2)
            return third is not None and third.value in {"vector", "string"}
        return False

    # ---------- Выражения ----------

    def _parse_expr(self) -> TreeNode: #Точка входа для разбора выражений. 
        return self._parse_assign()#Разбирает присваивание, которое может быть цепочкой бинарных операторов с разным приоритетом.

    def _parse_assign(self) -> TreeNode:#Разбирает присваивание. Сначала разбирает левую часть как бинарное выражение с минимальным приоритетом 1
        #Затем проверяет, есть ли оператор присваивания (=, +=, и т.д.). Если есть, разбирает правую часть рекурсивно как другое присваивание. 
        left_expr = self._parse_binop(1)
        current_token = self.cur()
        if current_token is not None and current_token.type == "OPERATOR" and current_token.value in ASSIGN_OPS:
            operator = current_token.value
            self.idx += 1
            right_expr = self._parse_assign()
            return TreeNode("Assign", {"op": operator, "lhs": left_expr, "rhs": right_expr})
        return left_expr

    def _parse_binop(self, min_prec: int) -> TreeNode: #Разбирает бинарные операторы с приоритетом не меньше min_prec.
        left_expr = self._parse_unary()
        while True:
            current_token = self.cur()
            if current_token is None or current_token.type != "OPERATOR" or current_token.value not in OP_PRIORITY:
                break
            precedence = OP_PRIORITY[current_token.value]
            if precedence < min_prec:
                break
            operator = current_token.value
            self.idx += 1
            right_expr = self._parse_binop(precedence + 1)
            left_expr = TreeNode("BinOp", {"op": operator, "lhs": left_expr, "rhs": right_expr})
        return left_expr

    def _parse_unary(self) -> TreeNode: #Разбирает унарные операторы. Ожидает оператор (!, ++, +, -) и операнд. Возвращает узел UnaryOp.
        current_token = self.cur()
        if current_token is not None and current_token.type == "OPERATOR" and current_token.value in {"!", "++", "+", "-"}:
            operator = current_token.value
            self.idx += 1
            operand = self._parse_unary()
            return TreeNode("UnaryOp", {"op": operator, "prefix": True, "operand": operand})
        return self._parse_postfix()

    def _parse_postfix(self) -> TreeNode:#Разбирает постфиксные операторы и вызовы. Сначала разбирает атомарное выражение, затем в цикле проверяет, есть ли после него вызов (скобки), доступ к полю (точка) или постфиксный инкремент (++) и соответственно обновляет узел. Возвращает итоговый узел выражения.
        result_node = self._parse_atom()
        while True:
            if self._try_consume("DELIMITER", "("):
                call_arguments = self._parse_call_args()
                self._require_val(")", "закрывающая скобка вызова")
                result_node = TreeNode("Call", {"callee": result_node, "call_args": call_arguments})
                continue
            if self._try_consume("OPERATOR", "."):
                field_name = self._require("IDENTIFIER", hint="имя поля после '.'").value
                result_node = TreeNode("FieldAccess", {"obj": result_node, "field_name": field_name})
                continue
            if self._try_consume("OPERATOR", "++"):
                result_node = TreeNode("UnaryOp", {"op": "++", "prefix": False, "operand": result_node})
                continue
            break
        return result_node

    def _parse_call_args(self) -> List[TreeNode]: #Разбирает аргументы вызова функции. 
        call_arguments: List[TreeNode] = [] #Если сразу стоит закрывающая скобка, возвращает пустой список. Иначе, пока есть аргументы, разбирает выражение и добавляет его в результат
        if self._check_val(")"):
            return call_arguments
        while True:
            call_arguments.append(self._parse_expr())
            if not self._try_consume("DELIMITER", ","):
                break
        return call_arguments

    def _parse_atom(self) -> TreeNode: #Разбирает атомарные выражения: константы, идентификаторы, вызов static_cast и группирующие скобки. 
        current_token = self.cur() #Если токен не соответствует ни одному из этих вариантов, выбрасывает SyntaxError
        if current_token is None:
            raise self._make_error("неожиданный конец выражения", "идентификатор, константа или '('")

        if current_token.type in {"CONSTANT_INT", "CONSTANT_FLOAT", "CONSTANT_STRING", "CONSTANT_BOOL"}:
            self.idx += 1
            return TreeNode("Literal", {"lit_type": current_token.type, "lit_val": current_token.value})

        if current_token.type == "IDENTIFIER":
            identifier_name = current_token.value
            self.idx += 1
            if self._try_consume("OPERATOR", "::"):
                suffix = self._require("IDENTIFIER", hint="имя после '::'").value
                identifier_name = f"{identifier_name}::{suffix}"
            return TreeNode("Identifier", {"ident_name": identifier_name})

        if current_token.type == "KEYWORD" and current_token.value == "static_cast":
            self.idx += 1
            self._require("OPERATOR", "<", "открывающая '<' static_cast")
            cast_type = self._parse_type_node()
            self._require("OPERATOR", ">", "закрывающая '>' static_cast")
            self._require_val("(", "открывающая скобка static_cast")
            cast_expr = self._parse_expr()
            self._require_val(")", "закрывающая скобка static_cast")
            return TreeNode("Cast", {"cast_type": cast_type, "cast_expr": cast_expr})

        if self._try_consume("DELIMITER", "("):
            inner = self._parse_expr()
            self._require_val(")", "закрывающая скобка выражения")
            return TreeNode("Group", {"inner": inner})

        raise self._make_error(
            "неожиданный токен",
            "идентификатор, константа, static_cast или '('",
        )


# ---------- Вывод дерева ----------


def _val_to_str(v: Any) -> str: #Преобразует значение в строку для отображения в дереве. 
    if v is None: #Если значение None, возвращает "—". Если это булево, возвращает "да" или "нет". Иначе просто str(v).
        return "—"
    if isinstance(v, bool):
        return "да" if v else "нет"
    return str(v)


def render_tree(node: TreeNode) -> str: #Рекурсивно строит строковое представление дерева. 
    #Для каждого узла отображает его тег и затем его поля с отступами и ветвями. Использует символы "├── " и "└── " для отображения структуры дерева. 
    # Для списков отображает каждый элемент как отдельную ветвь. Для примитивных значений отображает их строковое представление.
    lines: List[str] = []

    def _draw_val(val: Any, prefix: str, branch: str, label: Optional[str] = None) -> None:
        lbl = f"{label}: " if label else ""
        if isinstance(val, TreeNode):
            lines.append(f"{prefix}{branch}{lbl}[{val.tag}]")
            _draw_fields(val, prefix + ("    " if branch == "└── " else "│   "))
        elif isinstance(val, list):
            if not val:
                lines.append(f"{prefix}{branch}{lbl}(пусто)")
                return
            lines.append(f"{prefix}{branch}{lbl}")
            child_pfx = prefix + ("    " if branch == "└── " else "│   ")
            for i, item in enumerate(val):
                ch_br = "└── " if i == len(val) - 1 else "├── "
                _draw_val(item, child_pfx, ch_br)
        else:
            lines.append(f"{prefix}{branch}{lbl}{_val_to_str(val)}")

    def _draw_fields(node: TreeNode, prefix: str) -> None:
        items = list(node.data.items())
        for i, (k, v) in enumerate(items):
            br = "└── " if i == len(items) - 1 else "├── "
            _draw_val(v, prefix, br, k)

    lines.append(f"[{node.tag}]")
    _draw_fields(node, "")
    return "\n".join(lines)



def _load_tokens(path: Path) -> List[Token]:
    data = json.loads(path.read_text(encoding="utf-8"))
    result: List[Token] = []
    for item in data:
        result.append(
            Token(item["type"], item["value"], int(item.get("line", 0)))
        )
    return result


def main() -> int:
    cli = argparse.ArgumentParser(
        description="Синтаксический анализатор (рекурсивный спуск) для test.cpp"
    )
    cli.add_argument("input", nargs="?", help="Путь к .cpp файлу")
    args = cli.parse_args()

    try:
        if args.tokens_json:
            token_stream = _load_tokens(Path(args.tokens_json))
        elif args.input:
            # прямой запуск через лексер
            sys.path.insert(0, str(Path(__file__).parent))
            from lexer import Lexer
            src = Path(args.input).read_text(encoding="utf-8")
            lex = Lexer(src)
            raw = lex.tokenize()
            SKIP = {"PREPROCESSOR", "ERROR"}
            KWORD_AS_IDENT = {"cout", "endl", "std", "namespace", "using"}
            token_stream = []
            for t in raw:
                if t.type in SKIP:
                    continue
                ttype = t.type
                if ttype == "STRING_LITERAL":
                    ttype = "CONSTANT_STRING"
                if ttype == "BOOL_CONST":
                    ttype = "CONSTANT_BOOL"
                if ttype == "KEYWORD" and t.value in KWORD_AS_IDENT:
                    ttype = "IDENTIFIER"
                token_stream.append(Token(ttype, t.value, t.line))
        else:
            print("[ОШИБКА] Укажите входной файл", file=sys.stderr)
            return 2

        print("─" * 60)
        print("ВХОДНОЙ ПОТОК ТОКЕНОВ:")
        print("─" * 60)
        print([(t.type, t.value) for t in token_stream])
        print()

        analyzer = SyntaxAnalyzer(token_stream)
        ast_root = analyzer.build_tree()
        tree_text = render_tree(ast_root)
        ast_json = json.dumps(ast_root.serialize(), ensure_ascii=False, indent=2)

        print("─" * 60)
        print("АБСТРАКТНОЕ СИНТАКСИЧЕСКОЕ ДЕРЕВО:")
        print("─" * 60)
        print(tree_text)
        print()
        print("✔ Синтаксический анализ завершён успешно. Ошибок не найдено.")

        return 0

    except SyntaxError as err:
        print(str(err), file=sys.stderr)
        print("✘ Синтаксический анализ завершён с ошибками.", file=sys.stderr)
        return 1
    except RuntimeError as err:
        print(f"[ОШИБКА] {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())