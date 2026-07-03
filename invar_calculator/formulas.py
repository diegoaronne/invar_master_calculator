"""Evaluación segura de fórmulas aritméticas.

Varios RF permiten capturar cantidades o costos como expresiones
(p. ej. "2/20" para mandos intermedios en cuadrillas — RF-04 video 14;
"1/vida_util" para llantas — RF-04 video 16; formulación de costo unitario
con índices — RF-03 video 13). Se evalúan con un intérprete restringido
basado en el AST de Python: solo aritmética y variables provistas.
"""
from __future__ import annotations

import ast
import operator
from decimal import Decimal
from typing import Mapping

from .precision import D, Numero

_OPERADORES_BIN = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}
_OPERADORES_UN = {ast.UAdd: operator.pos, ast.USub: operator.neg}


class FormulaInvalida(ValueError):
    """La expresión contiene elementos no permitidos o variables desconocidas."""


def evaluar_formula(expresion: str, variables: Mapping[str, Numero] | None = None) -> Decimal:
    """Evalúa una expresión aritmética y regresa Decimal.

    Solo se permiten números, + - * / ** %, paréntesis y los nombres
    incluidos en ``variables``.
    """
    variables = {k: D(v) for k, v in (variables or {}).items()}
    try:
        arbol = ast.parse(expresion, mode="eval")
    except SyntaxError as exc:
        raise FormulaInvalida(f"Expresión inválida: {expresion!r}") from exc

    def _eval(nodo: ast.AST) -> Decimal:
        if isinstance(nodo, ast.Expression):
            return _eval(nodo.body)
        if isinstance(nodo, ast.Constant):
            if isinstance(nodo.value, (int, float)):
                return D(nodo.value)
            raise FormulaInvalida(f"Constante no numérica en {expresion!r}")
        if isinstance(nodo, ast.Name):
            if nodo.id in variables:
                return variables[nodo.id]
            raise FormulaInvalida(f"Variable desconocida {nodo.id!r} en {expresion!r}")
        if isinstance(nodo, ast.BinOp) and type(nodo.op) in _OPERADORES_BIN:
            izq, der = _eval(nodo.left), _eval(nodo.right)
            return D(_OPERADORES_BIN[type(nodo.op)](izq, der))
        if isinstance(nodo, ast.UnaryOp) and type(nodo.op) in _OPERADORES_UN:
            return D(_OPERADORES_UN[type(nodo.op)](_eval(nodo.operand)))
        raise FormulaInvalida(f"Elemento no permitido en {expresion!r}")

    return _eval(arbol)
