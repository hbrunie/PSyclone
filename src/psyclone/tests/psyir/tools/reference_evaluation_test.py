from psyclone.psyir import nodes as nodes
from psyclone.psyir.frontend.fortran import FortranReader
from psyclone.psyir.tools.reference_evaluation import BooleanValue, ReferenceEvaluation

from typing import List, Dict
import os


def test_evaluate_unary_expr():
    expr = ".NOT. .True."
    reader = FortranReader()
    psyir_expr = reader.psyir_from_expression(expr)
    eval = ReferenceEvaluation()
    assert isinstance(psyir_expr, nodes.UnaryOperation)
    res: BooleanValue = eval._evaluate_unary_operation(psyir_expr)
    assert res == BooleanValue.ALWAYS_FALSE


def test_evaluate_static_true():
    reader = FortranReader()
    code = """subroutine foo()
    integer :: a
    if (.TRUE.) then
        a = 2 
    else
        a = 3 
    endif
    endsubroutine
    """
    psyir_tree: nodes.Node = reader.psyir_from_source(code)
    psyir_ifblock: nodes.IfBlock = psyir_tree.walk(nodes.IfBlock)[0]
    ## extract if condition expression
    psyir_node: nodes.Node = psyir_ifblock.children[0]

    eval = ReferenceEvaluation()
    assert isinstance(psyir_node, (nodes.Reference, nodes.Literal))
    evaluation: BooleanValue = eval.evaluate_as_boolean(psyir_node)
    assert evaluation == BooleanValue.ALWAYS_TRUE


def test_evaluate_static_false():
    reader = FortranReader()
    code = """subroutine foo()
    integer :: a
    if (.FALSE.) then
        a = 2 
    else
        a = 3 
    endif
    endsubroutine
    """
    psyir_tree: nodes.Node = reader.psyir_from_source(code)
    psyir_ifblock: nodes.IfBlock = psyir_tree.walk(nodes.IfBlock)[0]
    ## extract if condition expression
    psyir_node: nodes.Node = psyir_ifblock.children[0]

    eval = ReferenceEvaluation()
    assert isinstance(psyir_node, (nodes.Reference, nodes.Literal))
    evaluation: BooleanValue = eval.evaluate_as_boolean(psyir_node)
    assert evaluation == BooleanValue.ALWAYS_FALSE


def get_namelist_path() -> str:
    ## tools
    dirpath: str = os.path.dirname(__file__)
    ## psyir
    dirpath = os.path.dirname(dirpath)
    ## tests
    dirpath = os.path.dirname(dirpath)
    namelist_file_path = os.path.join(dirpath, "./test_files/nemo_namelist.nml")
    return namelist_file_path


def test_evaluate_from_namelist_true():
    reader = FortranReader()
    code = """subroutine foo()
    integer :: a
    logical :: ln_traqsr
    namelist /NAMSBC/ ln_traqsr
    if (ln_traqsr) then
        a = 2 
    else
        a = 3 
    endif
    endsubroutine
    """
    psyir_tree: nodes.Node = reader.psyir_from_source(code)
    psyir_ifblock: nodes.IfBlock = psyir_tree.walk(nodes.IfBlock)[0]
    ## extract if condition expression
    psyir_node: nodes.Node = psyir_ifblock.children[0]

    namelist_file_path = get_namelist_path()
    eval = ReferenceEvaluation(namelist_file_path)
    assert isinstance(psyir_node, (nodes.Reference, nodes.Literal))
    evaluation: BooleanValue = eval.evaluate_as_boolean(psyir_node)
    assert evaluation == BooleanValue.ALWAYS_TRUE


def test_evaluate_from_namelist_false():
    reader = FortranReader()
    code = """subroutine foo()
    integer :: a
    logical ::  ln_bt_auto
    namelist /NAMDYN_SPG/ ln_bt_auto
    if (ln_bt_auto) then
        a = 2 
    else
        a = 3 
    endif
    endsubroutine
    """
    psyir_tree: nodes.Node = reader.psyir_from_source(code)
    psyir_ifblock: nodes.IfBlock = psyir_tree.walk(nodes.IfBlock)[0]
    ## extract if condition expression
    psyir_node: nodes.Node = psyir_ifblock.children[0]

    namelist_file_path: str = get_namelist_path()
    eval = ReferenceEvaluation(namelist_file_path)
    assert isinstance(psyir_node, (nodes.Reference, nodes.Literal))
    evaluation: BooleanValue = eval.evaluate_as_boolean(psyir_node)
    assert evaluation == BooleanValue.ALWAYS_FALSE


def test_evaluate_parameter_true():
    reader = FortranReader()
    code = """subroutine foo()
    integer :: a
    logical, parameter :: param_var = .TRUE.
    if (param_var) then
        a = 2 
    else
        a = 3 
    endif
    endsubroutine
    """
    psyir_tree: nodes.Node = reader.psyir_from_source(code)
    psyir_ifblock: nodes.IfBlock = psyir_tree.walk(nodes.IfBlock)[0]
    routine_node: nodes.Routine = psyir_tree.walk(nodes.Routine)[0]
    ## extract if condition expression
    psyir_node: nodes.Node = psyir_ifblock.children[0]

    eval = ReferenceEvaluation()
    eval.update_parameter_table_from_symboltable(routine_node.symbol_table)
    assert isinstance(psyir_node, (nodes.Reference, nodes.Literal))
    evaluation: BooleanValue = eval.evaluate_as_boolean(psyir_node)
    assert evaluation == BooleanValue.ALWAYS_TRUE


def test_evaluate_parameter_false():
    reader = FortranReader()
    code = """subroutine foo()
    integer :: a
    logical, parameter :: param_var = .FALSE.
    if (param_var) then
        a = 2 
    else
        a = 3 
    endif
    endsubroutine
    """
    psyir_tree: nodes.Node = reader.psyir_from_source(code)
    psyir_ifblock: nodes.IfBlock = psyir_tree.walk(nodes.IfBlock)[0]
    routine_node: nodes.Routine = psyir_tree.walk(nodes.Routine)[0]
    ## extract if condition expression
    psyir_node: nodes.Node = psyir_ifblock.children[0]

    eval = ReferenceEvaluation()
    eval.update_parameter_table_from_symboltable(routine_node.symbol_table)
    assert isinstance(psyir_node, (nodes.Reference, nodes.Literal))
    evaluation: BooleanValue = eval.evaluate_as_boolean(psyir_node)
    assert evaluation == BooleanValue.ALWAYS_FALSE


def test_evaluate_from_complex_namelist():
    reader = FortranReader()
    code = """subroutine foo()
    integer :: a
    logical ::  ln_Iperio,ln_Jperio,ln_dynspg_ts   
    namelist /namusr_def/ ln_Iperio,ln_Jperio    

    if (ln_Iperio) then
        a = 2 
        if (.NOT. ln_Jperio) then
            a = 4 
        endif
    else
        a = 3 
    endif
    !! a == 4
    endsubroutine
    """
    psyir_tree: nodes.Node = reader.psyir_from_source(code)
    namelist_file_path = get_namelist_path()
    eval = ReferenceEvaluation(namelist_file_path)

    psyir_ifblock: nodes.IfBlock = psyir_tree.walk(nodes.IfBlock)[0]
    psyir_node: nodes.Node = psyir_ifblock.children[0]
    assert isinstance(psyir_node, (nodes.Reference, nodes.Literal))
    evaluation: BooleanValue = eval.evaluate_as_boolean(psyir_node)
    assert evaluation == BooleanValue.ALWAYS_TRUE

    psyir_ifblock: nodes.IfBlock = psyir_tree.walk(nodes.IfBlock)[1]
    ## Full If Condition expression
    psyir_node: nodes.Node = psyir_ifblock.children[0]
    assert isinstance(psyir_node, (nodes.UnaryOperation))
    evaluation: BooleanValue = eval.evaluate_as_boolean(psyir_node)
    assert evaluation == BooleanValue.ALWAYS_TRUE


def test_evaluate_from_complex_namelist_complex_expr():
    reader = FortranReader()
    code = """subroutine foo()
    integer :: b
    logical ::  ln_Iperio,ln_Jperio,ln_dynspg_ts   
    namelist /namusr_def/ ln_Iperio,ln_Jperio    ! Iperio is true / Jperio is false
    namelist /namdyn_spg/ ln_dynspg_ts   != .true.  split-explicit free surface

    b = 0
    if (ln_Iperio .and. (.NOT. ln_Jperio) .and. ln_dynspg_ts) then
        b = 1
    endif
    !!b == 1
    endsubroutine
    """
    psyir_tree: nodes.Node = reader.psyir_from_source(code)
    namelist_file_path = get_namelist_path()
    eval = ReferenceEvaluation(namelist_file_path)

    psyir_ifblock: nodes.IfBlock = psyir_tree.walk(nodes.IfBlock)[0]
    psyir_node: nodes.Node = psyir_ifblock.children[0]
    evaluation: BooleanValue = eval.evaluate_as_boolean(psyir_node)
    assert evaluation == BooleanValue.ALWAYS_TRUE


def test_evaluate_binary_expr():
    code = """
   MODULE stprk3_stg
   INTEGER,  PUBLIC, PARAMETER ::   np_LIN = 0 
   INTEGER,  PUBLIC, PARAMETER ::   np_IMP = 1 
   INTEGER,  PUBLIC, PARAMETER ::   np_HYB = 2 

   INTEGER  :: n_baro_upd =  np_HYB   
   CONTAINS
   ENDMODULE
    """

    reader = FortranReader()
    psyir_tree: nodes.Node = reader.psyir_from_source(code)
    node_module = psyir_tree.children[0]
    assert type(node_module) is nodes.Container
    namelist_file_path = get_namelist_path()
    eval = ReferenceEvaluation(namelist_file_path, module_node=node_module)
    expr = "n_baro_upd == np_hyb"
    reader = FortranReader()
    psyir_expr = reader.psyir_from_expression(expr)
    evaluation = eval.evaluate_as_boolean(psyir_expr)
    assert evaluation == BooleanValue.ALWAYS_TRUE
