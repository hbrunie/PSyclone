# -----------------------------------------------------------------------------
# BSD 3-Clause License
#
# Copyright (c) 2022-2024, Science and Technology Facilities Council.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
# -----------------------------------------------------------------------------
# Author: H. Brunie, University of Grenoble Alpes

"""Module providing a transformation that removes IfBlock if the condition is
known to be constant for the whole runtime execution."""

from psyclone.psyGen import Transformation
from psyclone.psyir.nodes import IfBlock, Routine, Node
from psyclone.psyir import nodes
from psyclone.psyir.symbols import ScalarType, SymbolTable
from psyclone.psyir.transformations.transformation_error import (
    TransformationError,
)
from enum import Enum
from typing import Dict, Optional, Union


class BooleanValue(Enum):
    UNKNOWN = 0
    DYNAMIC = 1
    ## STATIC
    ALWAYS_TRUE = 2
    ALWAYS_FALSE = 3


class Utils:
    @classmethod
    def get_integer_value_from_literal(cls, psyir_node: nodes.Literal) -> int:
        if psyir_node.datatype.intrinsic == ScalarType.Intrinsic.INTEGER:
            return int(psyir_node.value)
        else:
            raise Exception("Not a boolean literal")

    @classmethod
    def get_boolean_value_from_literal(cls, psyir_node: nodes.Literal) -> bool:
        if psyir_node.datatype.intrinsic == ScalarType.Intrinsic.BOOLEAN:
            if psyir_node.value == "true":
                return True
            else:
                assert psyir_node.value == "false"
                return False
        else:
            raise Exception("Not a boolean literal")


class RemoveIfBlockTrans(Transformation):

    def __init__(self, json_file_abspath: Optional[str] = None) -> None:
        super().__init__()
        self._known_reference_bool: Dict[str, bool] = {}
        self._known_reference_int: Dict[str, bool] = {}
        if json_file_abspath is not None:
            with open(json_file_abspath, "r") as inf:
                import json

                json_data = json.load(inf)
                if json_data.get("known_reference_bool") is None or json_data.get("known_reference_int") is None:
                    raise TransformationError(f"Wrong json data content: {json_file_abspath}.")
                else:
                    self._known_reference_bool = json_data["known_reference_bool"]
                    self._known_reference_int = json_data["known_reference_int"]

    def __str__(self) -> str:
        return "Remove IfBlock in psyir AST when this is safe to do."

    def _if_else_replace(self, main_schedule, if_block, if_body_schedule):
        """This code is extracted from Martin Schreiber MR#2801.
        Little helper routine to eliminate one branch of an IfBlock
        :param main_schedule: Schedule where if-branch is used
        :type main_schedule: Schedule
        :param if_block: If-else block itself
        :type if_block: IfBlock
        :param if_body_schedule: The body of the if or else block
        :type if_body_schedule: Schedule
        """

        from psyclone.psyir.nodes import Schedule

        assert isinstance(main_schedule, Schedule)
        assert isinstance(if_body_schedule, Schedule)

        # Obtain index in main schedule
        idx = main_schedule.children.index(if_block)

        # Detach it
        if_block.detach()

        # Insert childreen of if-body schedule
        for child in if_body_schedule.children:
            main_schedule.addchild(child.copy(), idx)
            idx += 1

    def if_else_replace(self, if_block: IfBlock, is_true: bool):
        if is_true:
            self._if_else_replace(if_block.parent, if_block, if_block.if_body)
        else:
            if if_block.else_body:
                self._if_else_replace(if_block.parent, if_block, if_block.else_body)
            else:
                if_block.detach()

    def _evaluate_literal(self, psyir_node: nodes.Literal, is_not: bool = False) -> BooleanValue:
        value: bool = Utils.get_boolean_value_from_literal(psyir_node)
        ## is_not XOR LiteralValue
        if is_not != value:
            return BooleanValue.ALWAYS_TRUE
        else:
            return BooleanValue.ALWAYS_FALSE

    def _evaluate_unary_operation(self, psyir_node: nodes.UnaryOperation, is_not: bool = False) -> BooleanValue:
        assert psyir_node._operator == nodes.UnaryOperation.Operator.NOT
        psyir_ref: nodes.Reference = psyir_node.children[0]
        return self.rec_evaluate(psyir_ref, is_not=(not is_not))

    def _not(self, boolean1: BooleanValue) -> BooleanValue:
        if boolean1 in (BooleanValue.DYNAMIC, BooleanValue.UNKNOWN):
            return boolean1
        elif boolean1 == BooleanValue.ALWAYS_TRUE:
            return BooleanValue.ALWAYS_FALSE
        else:
            assert boolean1 == BooleanValue.ALWAYS_FALSE
            return BooleanValue.ALWAYS_TRUE

    def _from_bool_to_boolean(self, expr: bool) -> BooleanValue:
        if expr:
            return BooleanValue.ALWAYS_TRUE
        else:
            return BooleanValue.ALWAYS_TRUE

    def _and(self, boolean1: BooleanValue, boolean2: BooleanValue) -> BooleanValue:
        if boolean1 in (BooleanValue.DYNAMIC, BooleanValue.UNKNOWN):
            return boolean1
        if boolean2 in (BooleanValue.DYNAMIC, BooleanValue.UNKNOWN):
            return boolean2
        if boolean1 == BooleanValue.ALWAYS_TRUE:
            return boolean2
        else:
            return boolean1

    def _or(self, boolean1: BooleanValue, boolean2: BooleanValue) -> BooleanValue:
        if boolean1 in (BooleanValue.DYNAMIC, BooleanValue.UNKNOWN):
            return boolean1
        if boolean2 in (BooleanValue.DYNAMIC, BooleanValue.UNKNOWN):
            return boolean2
        if boolean1 == BooleanValue.ALWAYS_TRUE:
            return boolean1
        else:
            return boolean2

    def _evaluate_equality(self, psyir_ref1: nodes.Reference, psyir_ref2: nodes.Reference) -> BooleanValue:
        name1 = psyir_ref1.name
        name2 = psyir_ref2.name
        boolvalue1 = self._known_boolean_table.get(name1)
        intvalue1 = self._known_int_table.get(name1)
        boolvalue2 = self._known_boolean_table.get(name2)
        intvalue2 = self._known_int_table.get(name2)
        if boolvalue1 is not None and boolvalue2 is not None:
            return self._from_bool_to_boolean(boolvalue1 == boolvalue2)
        elif intvalue1 is not None and intvalue2 is not None:
            return self._from_bool_to_boolean(intvalue1 == intvalue2)
        else:
            return BooleanValue.UNKNOWN

    def _evaluate_nonequality(self, psyir_ref1: nodes.Reference, psyir_ref2: nodes.Reference) -> BooleanValue:
        pass

    def _evaluate_binary_operation(self, psyir_node: nodes.BinaryOperation, is_not: bool = False) -> BooleanValue:
        boolean0: BooleanValue = self.rec_evaluate(psyir_node.children[0], is_not)
        boolean1: BooleanValue = self.rec_evaluate(psyir_node.children[1], is_not)
        if psyir_node.operator == nodes.BinaryOperation.Operator.AND:
            return self._not(self._and(boolean0, boolean1))
        elif psyir_node.operator == nodes.BinaryOperation.Operator.OR:
            return self._not(self._or(boolean0, boolean1))
        elif psyir_node.operator == nodes.BinaryOperation.Operator.EQ:
            assert len(psyir_node.children) == 2
            return self._evaluate_equality(psyir_node.children[0], psyir_node.children[1])
        elif psyir_node.operator == nodes.BinaryOperation.Operator.NE:
            assert len(psyir_node.children) == 2
            return self._evaluate_nonequality(psyir_node.children[0], psyir_node.children[1])
        else:
            raise Exception("Not supported.")

    def _evaluate_reference_as_known_bool_or_int(self, psyir_node: nodes.Reference) -> Union[bool, int]:
        var_name: str = psyir_node.name
        ## If it is found in NameList table, get its value
        if var_name in self._known_reference_bool:
            return self._known_reference_bool[var_name]
        ## if is parameter
        elif var_name in self._known_reference_int:
            return self._known_reference_int[var_name]
        else:
            raise TransformationError("Not in namelist not parameter table.")

    def _evaluate_single_reference(self, psyir_node: nodes.Reference, is_not: bool = False) -> Union[int,BooleanVal ue:]
        assert isinstance(psyir_node, nodes.Reference)
        try:
            value: Union[bool, int] = self._evaluate_reference_as_known_bool_or_int(psyir_node)
        except TransformationError as e:
            return BooleanValue.DYNAMIC

        if isinstance(value, int):
            return value
        else:
            assert isinstance(value, bool)
            ## Exclusive OR (XOR) between .NOT. (true or false) and the Reference
            if is_not != value:
                return BooleanValue.ALWAYS_TRUE
            else:
                return BooleanValue.ALWAYS_FALSE

    def rec_evaluate(self, psyir_node: nodes.Node, is_not: bool = False) -> BooleanValue:
        """Evaluate the boolean result of a psyir Reference.
        Either it is unknown, or dynamic (changes within code execution)
        or static: AlwaysTrue or AlwaysFalse

        :param psyir_node: _description_
        :type psyir_node: nodes.Node
        :return: _description_
        :rtype: bool
        """
        if isinstance(psyir_node, nodes.Literal):
            return self._evaluate_literal(psyir_node, is_not)
        elif isinstance(psyir_node, nodes.Reference):
            return self._evaluate_single_reference(psyir_node, is_not)
        elif isinstance(psyir_node, nodes.UnaryOperation):
            return self._evaluate_unary_operation(psyir_node, is_not)
        elif isinstance(psyir_node, nodes.BinaryOperation):
            return self._evaluate_binary_operation(psyir_node, is_not)
        else:
            raise TransformationError("Not implemented.")

    def evaluate(self, condition: Node) -> bool:
        boolean = self.rec_evaluate(condition)
        if boolean == BooleanValue.ALWAYS_TRUE:
            return True
        elif boolean == BooleanValue.ALWAYS_FALSE:
            return False
        else:
            raise TransformationError("Unknown or Dynamic condition.")

    def evaluate_with_sympy(self, condition: Node, sym_table: SymbolTable) -> bool:
        from psyclone.psyir.frontend.sympy_reader import SymPyReader
        from psyclone.psyir.backend.sympy_writer import SymPyWriter
        import sympy

        expr_sympy = SymPyWriter(condition)
        new_expr = sympy.simplify(expr_sympy)
        reader = SymPyReader(expr_sympy)

        psyir_expr: Node = reader.psyir_from_expression(new_expr, sym_table)
        print(psyir_expr.debug_string())
        return True

    def _eliminate_ifblock_if_const_condition(self, if_block: IfBlock):
        """Eliminate if-block if conditions are constant booleans.
        :rtype: None
        """

        condition = if_block.condition
        if isinstance(condition, nodes.Literal):  # .datatype.intrinsic is ScalarType.Intrinsic.BOOLEAN:
            if condition.value == "true":
                self.if_else_replace(if_block, is_true=True)
            else:
                self.if_else_replace(if_block, is_true=False)
        else:
            is_true = self.evaluate(condition)
            self.if_else_replace(if_block, is_true)

    def apply(self, node: Node, options=None):
        self.validate(node, options)
        for if_block in node.walk(IfBlock):
            self._eliminate_ifblock_if_const_condition(if_block)

    def validate(self, node: Node, options=None):
        if not isinstance(node, Routine):
            raise TransformationError("Only handles Routine node.")
