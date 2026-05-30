from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Типы данных C++ (поддерживаемое подмножество)
# ---------------------------------------------------------------------------
NUM_TYPES   = {"int", "long", "long long", "double"}
STREAM_KIND = "std::ostream"
VOID_KIND   = "void"
UNK_KIND    = "unknown"


# ---------------------------------------------------------------------------
# Запись таблицы символов
# ---------------------------------------------------------------------------
@dataclass
class Entry:
    ident:       str
    data_type:   str
    kind:        str      # variable / parameter / function / builtin
    region:      str
    is_declared: bool
    is_ready:    bool
    src_line:    int = 0
    signature:   str = ""


# ---------------------------------------------------------------------------
# Семантическая ошибка
# ---------------------------------------------------------------------------
@dataclass
class Issue:
    text: str
    line: int = 0

    def __str__(self) -> str:
        where = f"строка {self.line}: " if self.line else ""
        return f"Семантическая ошибка: {where}{self.text}"


# ---------------------------------------------------------------------------
# Триада промежуточного кода
# ---------------------------------------------------------------------------
@dataclass
class Triple:
    num:  int
    op:   str
    arg1: str
    arg2: str = ""

    def display(self) -> str:
        if self.arg2 != "":
            return f"{self.num}) ({self.op}, {self.arg1}, {self.arg2})"
        return f"{self.num}) ({self.op}, {self.arg1})"


# ---------------------------------------------------------------------------
# Область видимости
# ---------------------------------------------------------------------------
class Region:
    def __init__(self, label: str, outer: Optional["Region"] = None) -> None:
        self.label  = label
        self.outer  = outer
        self.table: Dict[str, Entry] = {}

    def lookup(self, name: str) -> Optional[Entry]:
        node: Optional[Region] = self
        while node is not None:
            if name in node.table:
                return node.table[name]
            node = node.outer
        return None


# ---------------------------------------------------------------------------
# Вспомогательные функции для работы с TreeNode
# TreeNode имеет: .tag (str) и .data (dict)
# ---------------------------------------------------------------------------
def _tag(node) -> str:
    """Тип узла TreeNode — хранится в node.tag."""
    return getattr(node, "tag", "?")

def _get(node, key, default=None):
    """Получить поле из node.data[key]."""
    if node is None:
        return default
    data = getattr(node, "data", {})
    return data.get(key, default)

def _type_name(type_node) -> str:
    """Извлечь строку типа из узла TypeNode."""
    return _get(type_node, "type_name", UNK_KIND) or UNK_KIND


# ---------------------------------------------------------------------------
# Главный класс анализатора
# ---------------------------------------------------------------------------
class Checker:

    def __init__(self) -> None:
        self.global_region  = Region("global")
        self.cur_region     = self.global_region
        self.issues:   List[Issue]  = []
        self.entries:  List[Entry]  = []
        self.triples:  List[Triple] = []
        self.fn_table: Dict[str, Entry] = {}
        self.cur_fn:   Optional[Entry]  = None
        self._region_cnt = 0
        self._register_builtins()

    # ------------------------------------------------------------------
    def _register_builtins(self) -> None:
        for name, dtype in [("std::cout", STREAM_KIND), ("std::endl", "std::string")]:
            e = Entry(name, dtype, "builtin", "global", True, True)
            self.global_region.table[name] = e
            self.entries.append(e)

    # ------------------------------------------------------------------
    def _report(self, msg: str, node=None) -> None:
        line = _get(node, "line", 0) or 0
        self.issues.append(Issue(msg, line))

    def _strip(self, t: str) -> str:
        return t.replace("const ", "").replace("&", "").strip()

    def _register(self, name: str, dtype: str, kind: str,
                  node, ready: bool, sig: str = "") -> Entry:
        if name in self.cur_region.table:
            self._report(
                f"повторное объявление идентификатора '{name}' "
                f"в области видимости '{self.cur_region.label}'", node)
            return self.cur_region.table[name]
        rec = Entry(name, dtype, kind, self.cur_region.label, True, ready, 0, sig)
        self.cur_region.table[name] = rec
        self.entries.append(rec)
        return rec

    def _open_region(self, prefix: str) -> None:
        self._region_cnt += 1
        self.cur_region = Region(f"{prefix}_{self._region_cnt}", self.cur_region)

    def _close_region(self) -> None:
        if self.cur_region.outer is not None:
            self.cur_region = self.cur_region.outer

    # ------------------------------------------------------------------
    # Триады
    # ------------------------------------------------------------------
    def _next_num(self) -> int:
        return len(self.triples) + 1

    def _ref(self, idx: int) -> str:
        return f"^{idx}"

    def _emit(self, op: str, a1: str, a2: str = "") -> str:
        t = Triple(self._next_num(), op, a1, a2)
        self.triples.append(t)
        return self._ref(t.num)

    def _patch(self, idx: int,
               a1: Optional[str] = None, a2: Optional[str] = None) -> None:
        t = self.triples[idx - 1]
        if a1 is not None: t.arg1 = a1
        if a2 is not None: t.arg2 = a2

    # ------------------------------------------------------------------
    # Точка входа
    # ------------------------------------------------------------------
    def analyze(self, ast) -> Tuple[List[Entry], List[Issue], List[Triple]]:
        return self.run(ast)

    def run(self, ast) -> Tuple[List[Entry], List[Issue], List[Triple]]:
        if _tag(ast) != "Program":
            self._report(f"корень AST должен быть Program, получен '{_tag(ast)}'")
            return self.entries, self.issues, self.triples

        fns = _get(ast, "functions", []) or []
        for fn in fns:
            self._pre_declare_fn(fn)  # объявить заголовок
            self._check_fn(fn)        # сразу проверить тело

        return self.entries, self.issues, self.triples

    # ------------------------------------------------------------------
    # Функции
    # ------------------------------------------------------------------
    def _pre_declare_fn(self, fn) -> None:
        fname  = _get(fn, "func_name", "?")
        rtype  = _type_name(_get(fn, "ret_type"))
        params = _get(fn, "params", []) or []
        sig    = "(" + ", ".join(_type_name(_get(p, "param_type")) for p in params) + ")"
        rec    = self._register(fname, rtype, "function", fn, True, sig)
        self.fn_table[fname] = rec

    def _check_fn(self, fn) -> None:
        fname = _get(fn, "func_name", "?")
        self.cur_fn = self.fn_table.get(fname)
        self._open_region(f"fn_{fname}")
        for param in (_get(fn, "params", []) or []):
            pname = _get(param, "param_name", "?")
            ptype = _type_name(_get(param, "param_type"))
            self._register(pname, ptype, "parameter", param, True)
        self._check_block(_get(fn, "body"), make_scope=False)
        self._close_region()
        self.cur_fn = None

    # ------------------------------------------------------------------
    # Блок и операторы
    # ------------------------------------------------------------------
    def _check_block(self, block, make_scope: bool = True) -> None:
        if block is None:
            return
        if make_scope:
            self._open_region("block")
        for stmt in (_get(block, "stmts", []) or []):
            self._check_stmt(stmt)
        if make_scope:
            self._close_region()

    def _check_stmt(self, stmt) -> None:
        k = _tag(stmt)

        if k == "Block":
            self._check_block(stmt)

        elif k == "Var":
            for decl in (_get(stmt, "decls", []) or []):
                self._check_var_decl(decl)

        elif k == "VarDecl":
            self._check_var_decl(stmt)

        elif k == "If":
            ctype, cplace = self._check_expr(_get(stmt, "cond"))
            if not self._is_cond(ctype):
                self._report(
                    f"условие if должно быть bool или числовым, получен '{ctype}'", stmt)
            jf_idx = self._next_num()
            self._emit("if_false", cplace, "?")

            self._check_block_or_stmt(_get(stmt, "then_branch"))

            alt = _get(stmt, "else_branch")
            if alt is not None:
                jmp_idx = self._next_num()
                self._emit("goto", "?", "")
                alt_start = self._next_num()
                self._patch(jf_idx, a2=self._ref(alt_start))
                self._check_block_or_stmt(alt)
                self._patch(jmp_idx, a1=self._ref(self._next_num()))
            else:
                self._patch(jf_idx, a2=self._ref(self._next_num()))

        elif k == "For":
            self._open_region("for")
            init = _get(stmt, "init_node")
            if init is not None:
                if _tag(init) == "VarDecl":
                    self._check_var_decl(init)
                else:
                    self._check_expr(init)

            loop_top = self._next_num()
            jf_idx: Optional[int] = None
            cond = _get(stmt, "cond_node")
            if cond is not None:
                ctype, cplace = self._check_expr(cond)
                if not self._is_cond(ctype):
                    self._report(
                        f"условие for должно быть bool или числовым, получен '{ctype}'", stmt)
                jf_idx = self._next_num()
                self._emit("if_false", cplace, "?")

            self._check_block_or_stmt(_get(stmt, "loop_body"))

            step = _get(stmt, "step_node")
            if step is not None:
                self._check_expr(step)

            self._emit("goto", self._ref(loop_top), "")
            if jf_idx is not None:
                self._patch(jf_idx, a2=self._ref(self._next_num()))
            self._close_region()

        elif k == "RangeFor":
            self._open_region("range_for")
            itype, iplace = self._check_expr(_get(stmt, "iterable"))
            if not self._strip(itype).startswith("std::vector"):
                self._report(
                    f"range-for ожидает std::vector<T>, получен '{itype}'", stmt)
            var = _get(stmt, "loop_var")
            if var is not None:
                self._register(
                    _get(var, "var_name", "?"),
                    _type_name(_get(var, "var_type")),
                    "range variable", var, True)
            self._check_block_or_stmt(_get(stmt, "loop_body"))
            self._close_region()

        elif k == "While":
            loop_top = self._next_num()
            ctype, cplace = self._check_expr(_get(stmt, "cond"))
            if not self._is_cond(ctype):
                self._report(
                    f"условие while должно быть bool или числовым, получен '{ctype}'", stmt)
            jf_idx = self._next_num()
            self._emit("if_false", cplace, "?")
            self._check_block_or_stmt(_get(stmt, "loop_body"))
            self._emit("goto", self._ref(loop_top), "")
            self._patch(jf_idx, a2=self._ref(self._next_num()))

        elif k == "Return":
            ret_val = _get(stmt, "ret_val")
            if ret_val is None:
                rtype, rplace = VOID_KIND, ""
            else:
                rtype, rplace = self._check_expr(ret_val)
            expected = self.cur_fn.data_type if self.cur_fn else UNK_KIND
            if not self._assignable(expected, rtype):
                self._report(
                    f"тип возвращаемого значения '{rtype}' "
                    f"несовместим с типом функции '{expected}'", stmt)
            self._emit("return", rplace, "")

        elif k == "ExprStmt":
            self._check_expr(_get(stmt, "expr"))

        else:
            self._report(f"неподдерживаемый оператор AST '{k}'", stmt)

    def _check_block_or_stmt(self, node) -> None:
        if node is None:
            return
        if _tag(node) == "Block":
            self._check_block(node)
        else:
            self._check_stmt(node)

    # ------------------------------------------------------------------
    # Объявление переменной
    # ------------------------------------------------------------------
    def _check_var_decl(self, decl) -> None:
        vname = _get(decl, "var_name", "?")
        vtype = _type_name(_get(decl, "var_type"))
        init  = _get(decl, "init_val")
        ready = init is not None or self._strip(vtype).startswith("std::")
        rec   = self._register(vname, vtype, "variable", decl, ready)
        if init is not None:
            itype, iplace = self._check_expr(init)
            if not self._assignable(vtype, itype):
                self._report(
                    f"тип инициализатора '{itype}' "
                    f"несовместим с типом переменной '{vtype}'", decl)
            rec.is_ready = True
            self._emit(":=", vname, iplace)

    # ------------------------------------------------------------------
    # Выражения
    # ------------------------------------------------------------------
    def _check_expr(self, expr) -> Tuple[str, str]:
        if expr is None:
            return UNK_KIND, "?"

        k = _tag(expr)

        if k == "Literal":
            lkind = _get(expr, "lit_type", "")
            val   = str(_get(expr, "lit_val", "?"))
            if lkind == "CONSTANT_INT":    return "int",        val
            if lkind == "CONSTANT_FLOAT":  return "double",     val
            if lkind == "CONSTANT_BOOL":   return "bool",       val
            if lkind == "CONSTANT_STRING":
                return ("char", val) if val.startswith("'") else ("std::string", val)
            return UNK_KIND, val

        if k == "Identifier":
            name = _get(expr, "ident_name", "?")
            rec  = self.cur_region.lookup(name) or self.global_region.lookup(name)
            if rec is None:
                if name in self.fn_table:
                    return self.fn_table[name].data_type, name
                self._report(
                    f"использование необъявленного идентификатора '{name}'", expr)
                return UNK_KIND, name
            if rec.kind in {"variable", "parameter"} and not rec.is_ready:
                self._report(
                    f"использование неинициализированной переменной '{name}'", expr)
            return rec.data_type, name

        if k == "Group":
            return self._check_expr(_get(expr, "inner"))

        if k == "UnaryOp":
            otype, oplace = self._check_expr(_get(expr, "operand"))
            op = _get(expr, "op", "?")
            if op == "!":
                if not self._is_cond(otype):
                    self._report(f"оператор ! неприменим к типу '{otype}'", expr)
                return "bool", self._emit("!", oplace)
            if op == "++":
                if self._strip(otype) not in NUM_TYPES:
                    self._report(
                        f"оператор ++ применим только к числовым типам, получен '{otype}'", expr)
                return otype, self._emit("++", oplace)
            if op in {"+", "-"}:
                if self._strip(otype) not in NUM_TYPES:
                    self._report(
                        f"унарный {op} применим только к числовым типам, получен '{otype}'", expr)
                return otype, self._emit(op, oplace)
            return otype, self._emit(op, oplace)

        if k == "BinOp":
            op    = _get(expr, "op", "?")
            ltype, lplace = self._check_expr(_get(expr, "lhs"))
            rtype, rplace = self._check_expr(_get(expr, "rhs"))
            res   = self._bin_type(op, ltype, rtype, expr)
            return res, self._emit(op, lplace, rplace)

        if k == "Assign":
            lhs   = _get(expr, "lhs")
            op    = _get(expr, "op", "=")
            ltype, lplace = self._check_lval(lhs)
            rtype, rplace = self._check_expr(_get(expr, "rhs"))
            if not self._assignable(ltype, rtype):
                self._report(
                    f"тип правой части '{rtype}' "
                    f"несовместим с типом левой части '{ltype}'", expr)
            self._mark_ready(lhs)
            return ltype, self._emit(":=" if op == "=" else op, lplace, rplace)

        if k == "Call":
            return self._check_call(expr)

        if k == "Cast":
            _, src_place = self._check_expr(_get(expr, "cast_expr"))
            target = _type_name(_get(expr, "cast_type"))
            return target, self._emit("cast " + target, src_place)

        if k == "FieldAccess":
            otype, oplace = self._check_expr(_get(expr, "obj"))
            field = _get(expr, "field_name", "?")
            return self._member_type(otype, field), f"{oplace}.{field}"

        self._report(f"неподдерживаемое выражение AST '{k}'", expr)
        return UNK_KIND, "?"

    def _check_lval(self, expr) -> Tuple[str, str]:
        if expr is None:
            return UNK_KIND, "?"
        if _tag(expr) == "Identifier":
            name = _get(expr, "ident_name", "?")
            rec  = self.cur_region.lookup(name) or self.global_region.lookup(name)
            if rec is None:
                self._report(
                    f"присваивание необъявленному идентификатору '{name}'", expr)
                return UNK_KIND, name
            return rec.data_type, name
        if _tag(expr) == "FieldAccess":
            return self._check_expr(expr)
        self._report("левая часть присваивания должна быть идентификатором", expr)
        return self._check_expr(expr)

    def _mark_ready(self, expr) -> None:
        if expr is not None and _tag(expr) == "Identifier":
            name = _get(expr, "ident_name", "?")
            rec  = (self.cur_region.lookup(name)
                    or self.global_region.lookup(name))
            if rec is not None:
                rec.is_ready = True

    # ------------------------------------------------------------------
    # Вызов функции
    # ------------------------------------------------------------------
    def _check_call(self, expr) -> Tuple[str, str]:
        callee  = _get(expr, "callee")
        args    = _get(expr, "call_args", []) or []
        evaled  = [self._check_expr(a) for a in args]
        atypes  = [t for t, _ in evaled]
        aplaces = [p for _, p in evaled]

        if callee is not None and _tag(callee) == "Identifier":
            fname = _get(callee, "ident_name", "?")
            if fname not in self.fn_table:
                self._report(f"вызов необъявленной функции '{fname}'", callee)
                return UNK_KIND, self._emit("call " + fname, ", ".join(aplaces))
            fn  = self.fn_table[fname]
            exp = self._parse_sig(fn.signature)
            if len(exp) != len(atypes):
                self._report(
                    f"функция '{fname}' ожидает {len(exp)} арг., "
                    f"получено {len(atypes)}", callee)
            else:
                for i, (want, got) in enumerate(zip(exp, atypes), 1):
                    if not self._assignable(want, got):
                        self._report(
                            f"аргумент {i} функции '{fname}' имеет тип '{got}', "
                            f"ожидался '{want}'", callee)
            return fn.data_type, self._emit("call " + fname, ", ".join(aplaces))

        ctype, cplace = self._check_expr(callee)
        return ctype, self._emit("call " + cplace, ", ".join(aplaces))

    def _parse_sig(self, sig: str) -> List[str]:
        sig = sig.strip()
        if not (sig.startswith("(") and sig.endswith(")")):
            return []
        inside = sig[1:-1].strip()
        return [] if not inside else [p.strip() for p in inside.split(",")]

    # ------------------------------------------------------------------
    # Работа с типами
    # ------------------------------------------------------------------
    def _member_type(self, otype: str, member: str) -> str:
        norm = self._strip(otype)
        if norm == STREAM_KIND:
            return STREAM_KIND
        if norm.startswith("std::vector"):
            if member == "empty":     return "bool"
            if member == "size":      return "int"
            if member == "push_back": return VOID_KIND
        return UNK_KIND

    def _bin_type(self, op: str, lt: str, rt: str, node) -> str:
        ln, rn = self._strip(lt), self._strip(rt)
        if op == "<<":
            return STREAM_KIND if ln == STREAM_KIND or ln == UNK_KIND else lt
        if op in {"+", "-", "*", "/", "%"}:
            if ln in NUM_TYPES and rn in NUM_TYPES:
                if op == "%" and "double" in {ln, rn}:
                    self._report("оператор % применим только к целочисленным типам", node)
                if "double"    in {ln, rn}: return "double"
                if "long long" in {ln, rn}: return "long long"
                return "int"
            self._report(
                f"оператор {op} ожидает числовые операнды, "
                f"получены '{lt}' и '{rt}'", node)
            return UNK_KIND
        if op in {"<", "<=", ">", ">=", "==", "!="}:
            if self._comparable(lt, rt):
                return "bool"
            self._report(f"оператор {op} неприменим к типам '{lt}' и '{rt}'", node)
            return "bool"
        if op in {"&&", "||"}:
            if self._is_cond(lt) and self._is_cond(rt):
                return "bool"
            self._report(
                f"логический оператор {op} ожидает bool/числовые операнды, "
                f"получены '{lt}' и '{rt}'", node)
            return "bool"
        return UNK_KIND

    def _is_cond(self, t: str) -> bool:
        n = self._strip(t)
        return n in NUM_TYPES or n == "bool" or n == UNK_KIND

    def _comparable(self, lt: str, rt: str) -> bool:
        ln, rn = self._strip(lt), self._strip(rt)
        return (ln == UNK_KIND or rn == UNK_KIND
                or ln == rn
                or (ln in NUM_TYPES and rn in NUM_TYPES))

    def _assignable(self, target: str, source: str) -> bool:
        t, s = self._strip(target), self._strip(source)
        if t == UNK_KIND or s == UNK_KIND:          return True
        if t == s:                                   return True
        if t == "double"    and s in NUM_TYPES:      return True
        if t == "long long" and s in {"int", "long"}: return True
        if t == "bool"      and s == "bool":         return True
        return False


# ---------------------------------------------------------------------------
# Форматирование вывода
# ---------------------------------------------------------------------------
def entries_to_text(entries: List[Entry]) -> str:
    hdr = (f"{'Имя':<20} | {'Тип':<14} | {'Вид':<14} | "
           f"{'Область':<22} | {'Объявл.':<7} | Иниц.")
    rows = [hdr, "-" * len(hdr)]
    for e in entries:
        rows.append(
            f"{e.ident:<20} | {e.data_type:<14} | {e.kind:<14} | "
            f"{e.region:<22} | {str(e.is_declared):<7} | {e.is_ready}")
    return "\n".join(rows)


def triples_to_text(triples: List[Triple]) -> str:
    return "\n".join(t.display() for t in triples)


# ---------------------------------------------------------------------------
# Публичные псевдонимы для run.py
# ---------------------------------------------------------------------------
def SemanticAnalyzer() -> Checker:  # noqa: N802
    return Checker()

def symbols_to_text(entries: List[Entry]) -> str:
    return entries_to_text(entries)