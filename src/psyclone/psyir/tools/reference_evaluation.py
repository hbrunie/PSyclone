from psyclone.psyir import nodes
from psyclone.psyir.symbols import (
    Symbol,
    SymbolTable,
    DataType,
    UnresolvedType,
    ScalarType,
    DataSymbol,
)
from psyclone.parse import ModuleManager
from psyclone.errors import PSycloneError
import f90nml

from typing import Dict, Union, List, Optional, Tuple
from enum import Enum


class RefEvalError(PSycloneError):
    """Provides a PSyclone-specific error class for errors related to a
    PSyIR visitor.

    :param str value: Error message.

    """

    def __init__(self, value):
        PSycloneError.__init__(self, value)
        self.value = "ReferenceEvaluation Error: " + str(value)


class BooleanValue(Enum):
    UNKNOWN = 0
    DYNAMIC = 1
    ## STATIC
    ALWAYS_TRUE = 2
    ALWAYS_FALSE = 3


## Solution from
# https://stackoverflow.com/questions/24481852/serialising-an-enum-member-to-json/24482806#24482806
import json

PUBLIC_ENUMS = {
    "BooleanValue": BooleanValue,
    # ...
}


class EnumEncoder(json.JSONEncoder):
    def default(self, o):
        if type(o) in PUBLIC_ENUMS.values():
            return {"__enum__": str(o)}
        return json.JSONEncoder.default(self, o)


def as_enum(d):
    if "__enum__" in d:
        name, member = d["__enum__"].split(".")
        return getattr(PUBLIC_ENUMS[name], member)
    else:
        return d


class ReferenceEvaluation:
    def __init__(
        self,
        file_path: Optional[str] = None,
        routine_node: Optional[nodes.Routine] = None,
        module_node: Optional[nodes.Container] = None,
    ) -> None:
        self._parameter_boolean_table: Dict[str, bool] = {}
        self._namelist_boolean_table: Dict[str, bool] = {}
        self._namelist_int_table: Dict[str, bool] = {}
        self._parameter_int_table: Dict[str, int] = {}
        self._simple_assignment_table: Dict[str, List[str]] = {}
        self._dynamic_table: Dict[str, nodes.Reference] = {}
        if file_path is not None:
            self._namelist_boolean_table = self.get_namelist_table_from_fpath(file_path)
        if module_node is not None:
            assert isinstance(module_node.symbol_table, SymbolTable)
            self.update_parameter_table_from_symboltable(module_node.symbol_table)
        if routine_node is not None:
            self.complete_update_from_routine(routine_node=routine_node)
        self._known_boolean_table, self._known_int_table = self._merge_dictionaries()

    def _merge_dictionaries(self) -> Tuple[Dict[str, bool], Dict[str, int]]:
        d = {}
        for k, v in self._namelist_boolean_table.items():
            assert d.get(k) is None
            d[k] = v
        for k, v in self._parameter_boolean_table.items():
            assert d.get(k) is None
            d[k] = v
        _known_boolean_table = d
        d = {}
        for k, v in self._namelist_int_table.items():
            assert d.get(k) is None
            d[k] = v
        for k, v in self._parameter_int_table.items():
            assert d.get(k) is None
            d[k] = v
        _known_int_table = d
        return _known_boolean_table, _known_int_table

    def _get_integer_value_from_literal(self, psyir_node: nodes.Literal) -> int:
        if psyir_node.datatype.intrinsic == ScalarType.Intrinsic.INTEGER:
            return int(psyir_node.value)
        else:
            raise RefEvalError("Not a boolean literal")

    def _get_boolean_value_from_literal(self, psyir_node: nodes.Literal) -> bool:
        if psyir_node.datatype.intrinsic == ScalarType.Intrinsic.BOOLEAN:
            if psyir_node.value == "true":
                return True
            else:
                assert psyir_node.value == "false"
                return False
        else:
            raise RefEvalError("Not a boolean literal")

    def _propagate_parameter_value(self):
        for k, v in self._simple_assignment_table.items():
            if v in self._parameter_boolean_table:
                assert k not in self._parameter_boolean_table
                assert v not in self._namelist_boolean_table
                assert v not in self._dynamic_table
                self._parameter_boolean_table[k] = self._parameter_boolean_table[v]
            if v in self._parameter_int_table:
                assert k not in self._parameter_int_table
                assert v not in self._namelist_boolean_table
                assert v not in self._dynamic_table
                self._parameter_int_table[k] = self._parameter_int_table[v]
            elif v in self._namelist_boolean_table:
                assert k not in self._namelist_boolean_table
                assert v not in self._namelist_boolean_table
                self._namelist_boolean_table[k] = self._namelist_boolean_table[v]
            else:
                import warnings

                warnings.warn(f"Single assignment of {k} with UNKNOWN value: {v}")

    def complete_update_from_routine(self, routine_node: nodes.Routine):
        assert isinstance(routine_node.symbol_table, SymbolTable)
        self.update_parameter_table_from_symboltable(routine_node.symbol_table)
        self.update_simple_assignment_table(routine_node)
        self._propagate_parameter_value()

    def update_parameter_table_from_symboltable(self, symbol_table: SymbolTable):
        for datasym in symbol_table.datasymbols:
            datasym: DataSymbol
            ## Ignore non scalartype data
            if not isinstance(datasym.datatype, ScalarType):
                continue
            if datasym.is_constant:
                if datasym.datatype.intrinsic == ScalarType.Intrinsic.BOOLEAN:
                    assert self._parameter_boolean_table.get(datasym.name) is None
                    assert isinstance(datasym.initial_value, nodes.Literal)
                    value = self._get_boolean_value_from_literal(datasym.initial_value)
                    self._parameter_boolean_table[datasym.name] = value
                elif datasym.datatype.intrinsic == ScalarType.Intrinsic.INTEGER:
                    assert self._parameter_boolean_table.get(datasym.name) is None
                    if datasym.initial_value:
                        assert isinstance(datasym.initial_value, nodes.Literal)
                        value: int = self._get_integer_value_from_literal(datasym.initial_value)
                        self._parameter_int_table[datasym.name] = value
                    else:
                        import warnings

                        warnings.warn(f"No initial value for constant:{datasym.name}")
                else:
                    import warnings

                    warnings.warn(f"Not supported {datasym.datatype.intrinsic}")
            elif isinstance(datasym.initial_value, nodes.Reference):
                ref_name = datasym.initial_value.name
                if ref_name in self._parameter_int_table:
                    value = self._parameter_int_table[ref_name]
                    self._parameter_int_table[datasym.name] = value
                elif ref_name in self._parameter_boolean_table:
                    value = self._parameter_boolean_table[ref_name]
                    self._parameter_int_table[datasym.name] = value
                else:
                    import warnings

                    warnings.warn("Not impolemented")
            else:
                import warnings

                warnings.warn("Not impolemented")

    def _evaluate_literal(self, psyir_node: nodes.Literal, is_not: bool = False) -> BooleanValue:
        value: bool = self._get_boolean_value_from_literal(psyir_node)
        ## is_not XOR LiteralValue
        if is_not != value:
            return BooleanValue.ALWAYS_TRUE
        else:
            return BooleanValue.ALWAYS_FALSE

    def _evaluate_unary_operation(self, psyir_node: nodes.UnaryOperation, is_not: bool = False) -> BooleanValue:
        assert psyir_node._operator == nodes.UnaryOperation.Operator.NOT
        psyir_ref: nodes.Reference = psyir_node.children[0]
        return self.evaluate_as_boolean(psyir_ref, is_not=(not is_not))

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
        boolean0: BooleanValue = self.evaluate_as_boolean(psyir_node.children[0], is_not)
        boolean1: BooleanValue = self.evaluate_as_boolean(psyir_node.children[1], is_not)
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
            raise RefEvalError("Not supported.")

    def _evaluate_reference_in_nml_or_parameter(self, psyir_node: nodes.Reference) -> bool:
        var_name: str = psyir_node.name
        ## If it is found in NameList table, get its value
        if var_name in self._namelist_boolean_table:
            return self._namelist_boolean_table[var_name]
        ## if is parameter
        elif var_name in self._parameter_boolean_table:
            return self._parameter_boolean_table[var_name]
        else:
            raise RefEvalError("Not in namelist not parameter table.")

    def _evaluate_single_reference(self, psyir_node: nodes.Reference, is_not: bool = False) -> BooleanValue:
        assert isinstance(psyir_node, nodes.Reference)
        try:
            value: bool = self._evaluate_reference_in_nml_or_parameter(psyir_node)
        except RefEvalError as e:
            if psyir_node.name in self._dynamic_table:
                return BooleanValue.DYNAMIC
            else:
                return BooleanValue.UNKNOWN
        ## Exclusive OR (XOR) between .NOT. (true or false) and the Reference
        if is_not != value:
            return BooleanValue.ALWAYS_TRUE
        else:
            return BooleanValue.ALWAYS_FALSE

    def evaluate_as_boolean(self, psyir_node: nodes.Node, is_not: bool = False) -> BooleanValue:
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
            raise RefEvalError("Not implemented.")

    def remove_obsolete_if_conditions(self, module_manager: ModuleManager):
        pass
        ## for each conditional stmt in code
        ## Check only conditional stmt concerned:
        ### Walk through the code from entry subroutine
        #### Then into all kept called subroutine.
        ## Check if variable is in known constant variables
        ## If it is not: do nothing (keep condition)
        ## If it is, solve it:
        ### if True, remove condition, keep block
        ### if False, remove condition and remove block

    def get_namelist_table_from_fpath(self, fpath: str) -> Dict[str, bool]:
        d = self.get_flatten_var_dict_from_fname(fpath)
        namelist_table: Dict[str, bool] = {}
        for k, v in d.items():
            if isinstance(v, bool):
                assert namelist_table.get(k) is None, "Should not exist already"
                namelist_table[k] = v
        return namelist_table

    def get_flatten_var_dict_from_fname(self, fpath: str) -> Dict[str, dict]:
        """Returns dictionary from namelist file

        :param fname: Namelist Fortran file
        :type fname: str
        :return: Dictionnary of variables defined in namelist
        :rtype: Dict[str, dict]
        """
        fname_var_nl_obj = f90nml.read(fpath)  # the namelist object
        fname_var_namelist_dict = fname_var_nl_obj.todict()  # translate to dict
        flatten_dict = {}
        for k, v in fname_var_namelist_dict.items():
            for k1, v1 in v.items():
                flatten_dict[k1] = v1
        return flatten_dict

    def extract_var_symbols_from_ifblocks(self, psyir_tree: nodes.Node) -> Dict[str, Symbol]:
        """* From psyir_tree walk all IfBlock
            * for each IfBlock walk Reference
                * for each Reference keep symbol in result dictionary
        :param psyir_tree: entry point in psyir tree
        :type psyir_tree: nodes.Node
        :return: Dictionnry with keys being variables name and values are symbols
        :rtype: Dict[str, Symbol]
        """
        var_symbols = {}
        for n, ifcond in enumerate(psyir_tree.walk(nodes.IfBlock)):
            refs = ifcond.children[0].walk(nodes.Reference)
            for ref in refs:
                ref: nodes.Reference
                var_symbol_str = ref.symbol.name
                ref_symbol = ref.symbol
                var_symbols[var_symbol_str] = ref_symbol
        return var_symbols

    def is_namelist_varname(self, sym: Union[Symbol, nodes.Reference]):
        """NEMO namelist var start with
        ln: logical
        nn: integer
        rn: real
        cn: filename (complex?)

        :param sym: variable symbol to evaluate
        :type sym: Symbol
        :return: _description_
        :rtype: _type_
        """
        if type(sym) is nodes.Reference:
            sym = sym.symbol
        if (
            sym.name.startswith("ln_")
            or sym.name.startswith("cn_")
            or sym.name.startswith("rn_")
            or sym.name.startswith("nn_")
        ):
            return True
        else:
            return False

    def symbol_value_should_be_known(self, v: Symbol) -> bool:
        if v.is_static or v.is_argument or v.is_import:
            return True
        else:
            return False

    def find_boolean_variable(self, psyir_tree: nodes.Node) -> Dict[str, nodes.Reference]:
        """Does not handle RHS expression.
        only simple var = BOOLEAN (.FALSE. or .TRUE.)

        :param psyir_tree: _description_
        :type psyir_tree: nodes.Node
        :return: _description_
        :rtype: Dict[str, Reference]
        """
        res_dict = {}
        for assignment in psyir_tree.walk(nodes.Assignment):
            assignment: nodes.Assignment
            boolean = assignment.rhs
            if isinstance(boolean, nodes.Reference):
                if isinstance(boolean.datatype, DataType):
                    dt = boolean.datatype
                    if type(dt) is not UnresolvedType:
                        # dt: DataSymbol
                        assert type(dt) is ScalarType, print(type(dt))
                        if dt.intrinsic.name == "BOOLEAN":
                            res_dict[boolean.symbol.name] = "boolean"
        return res_dict

    def update_simple_assignment_table(self, psyir_tree: nodes.Node):
        for assignment in psyir_tree.walk(nodes.Assignment):
            assignment: nodes.Assignment
            ## one-level depth assignment
            if isinstance(assignment.rhs, nodes.Reference):
                assert isinstance(assignment.lhs, nodes.Reference)
                key: str = assignment.lhs.name
                empty_list: List[str] = []
                current_value: List[str] = self._simple_assignment_table.get(key, empty_list)
                rhs_name = assignment.rhs.name
                if rhs_name not in current_value:
                    self._simple_assignment_table[key] = current_value + [rhs_name]

        ## Check all single assignment to this variable don't change it
        new_dictionnary = {}
        for key, name_list in self._simple_assignment_table.items():
            ## Stronger:
            assert len(name_list) == 1
            current_name: str = name_list[0]
            for name in name_list:
                assert current_name == name
            new_dictionnary[key] = current_name
        self._simple_assignment_table = new_dictionnary
