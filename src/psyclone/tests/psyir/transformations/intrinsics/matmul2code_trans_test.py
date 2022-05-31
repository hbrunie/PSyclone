# -----------------------------------------------------------------------------
# BSD 3-Clause License
#
# Copyright (c) 2020-2022, Science and Technology Facilities Council.
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
# Authors R. W. Ford, A. R. Porter and S. Siso, STFC Daresbury Laboratory

'''Module containing tests for the matmul2code transformation.'''

import pytest
from psyclone.psyir.transformations import Matmul2CodeTrans, \
    TransformationError
from psyclone.psyir.transformations.intrinsics.matmul2code_trans import \
    _create_matrix_ref, _get_array_bound
from psyclone.psyir.nodes import BinaryOperation, Literal, ArrayReference, \
    Assignment, Reference, Range, KernelSchedule
from psyclone.psyir.symbols import DataSymbol, SymbolTable, ArrayType, \
    ScalarType, INTEGER_TYPE, REAL_TYPE
from psyclone.psyir.backend.fortran import FortranWriter
from psyclone.tests.utilities import Compile


def create_matmul():
    '''Utility function that creates a valid matmul node for use with
    subsequent tests.

    '''
    symbol_table = SymbolTable()
    one = Literal("1", INTEGER_TYPE)
    two = Literal("2", INTEGER_TYPE)
    index = DataSymbol("idx", INTEGER_TYPE, constant_value=3)
    symbol_table.add(index)
    array_type = ArrayType(REAL_TYPE, [5, 10, 15])
    mat_symbol = DataSymbol("x", array_type)
    symbol_table.add(mat_symbol)
    lbound1 = BinaryOperation.create(
        BinaryOperation.Operator.LBOUND, Reference(mat_symbol), one.copy())
    ubound1 = BinaryOperation.create(
        BinaryOperation.Operator.UBOUND, Reference(mat_symbol), one.copy())
    my_mat_range1 = Range.create(lbound1, ubound1, one.copy())
    lbound2 = BinaryOperation.create(
        BinaryOperation.Operator.LBOUND, Reference(mat_symbol), two.copy())
    ubound2 = BinaryOperation.create(
        BinaryOperation.Operator.UBOUND, Reference(mat_symbol), two.copy())
    my_mat_range2 = Range.create(lbound2, ubound2, one.copy())
    matrix = ArrayReference.create(mat_symbol, [my_mat_range1, my_mat_range2,
                                                Reference(index)])
    array_type = ArrayType(REAL_TYPE, [10, 20, 10])
    vec_symbol = DataSymbol("y", array_type)
    symbol_table.add(vec_symbol)
    lbound = BinaryOperation.create(
        BinaryOperation.Operator.LBOUND, Reference(vec_symbol), one.copy())
    ubound = BinaryOperation.create(
        BinaryOperation.Operator.UBOUND, Reference(vec_symbol), one.copy())
    my_vec_range = Range.create(lbound, ubound, one.copy())
    vector = ArrayReference.create(vec_symbol, [my_vec_range,
                                                Reference(index), one.copy()])
    matmul = BinaryOperation.create(
        BinaryOperation.Operator.MATMUL, matrix, vector)
    lhs_type = ArrayType(REAL_TYPE, [10])
    lhs_symbol = DataSymbol("result", lhs_type)
    symbol_table.add(lhs_symbol)
    lhs = Reference(lhs_symbol)
    assign = Assignment.create(lhs, matmul)
    KernelSchedule.create("my_kern", symbol_table, [assign])
    return matmul


def test_create_matrix_ref_1d():
    ''' Test that the _create_matrix_ref() utility works as expected for a
    1d array.

    '''
    array_type = ArrayType(REAL_TYPE, [10])
    array_symbol = DataSymbol("x", array_type)
    i_loop_sym = DataSymbol("i", INTEGER_TYPE)
    ref1 = _create_matrix_ref(array_symbol, [i_loop_sym], [])
    assert isinstance(ref1, ArrayReference)
    assert ref1.symbol is array_symbol
    assert len(ref1.indices) == 1
    assert ref1.indices[0].symbol is i_loop_sym


def test_create_matrix_ref_trailing_indices():
    ''' Test that the _create_matrix_ref() utility works as expected for an
    array that has an additional dimension that is not being looped over.

    '''
    array_type = ArrayType(REAL_TYPE, [10, 5])
    array_symbol = DataSymbol("x", array_type)
    i_loop_sym = DataSymbol("i", INTEGER_TYPE)
    k_sym = DataSymbol("k", INTEGER_TYPE)
    k_ref = Reference(k_sym)
    ref1 = _create_matrix_ref(array_symbol, [i_loop_sym], [k_ref])
    assert isinstance(ref1, ArrayReference)
    assert ref1.symbol is array_symbol
    assert len(ref1.indices) == 2
    assert ref1.indices[0].symbol is i_loop_sym
    # The second index should be a *copy* of the expression we supplied.
    assert ref1.indices[1].symbol is k_sym
    assert ref1.indices[1] is not k_ref


def test_create_matrix_ref_2d():
    ''' Test that the _create_matrix_ref() utility works as expected for a
    2d array.

    '''
    array_type = ArrayType(REAL_TYPE, [10, 8])
    array_symbol = DataSymbol("x", array_type)
    i_loop_sym = DataSymbol("i", INTEGER_TYPE)
    j_loop_sym = DataSymbol("j", INTEGER_TYPE)
    ref2 = _create_matrix_ref(array_symbol, [i_loop_sym, j_loop_sym], [])
    assert isinstance(ref2, ArrayReference)
    assert ref2.symbol is array_symbol
    assert len(ref2.indices) == 2
    assert ref2.indices[0].symbol is i_loop_sym
    assert ref2.indices[1].symbol is j_loop_sym


def test_get_array_bound_error():
    '''Test that the _get_array_bound() utility function raises the
    expected exception if the shape of the array's symbol is not
    supported.'''
    array_type = ArrayType(REAL_TYPE, [10])
    array_symbol = DataSymbol("x", array_type)
    reference = Reference(array_symbol)
    array_type._shape = [0.2]
    with pytest.raises(TransformationError) as excinfo:
        _get_array_bound(reference, 0)
    assert ("Transformation Error: Unsupported index type 'float' found for "
            "dimension 1 of array 'x'." in str(excinfo.value))


def test_get_array_bound():
    '''Test that the _get_array_bound utility function returns the expected
    bound values for different types of array declaration. Also checks that
    new nodes are created each time the utility is called.

    '''
    scalar_symbol = DataSymbol("n", INTEGER_TYPE, constant_value=20)
    array_type = ArrayType(REAL_TYPE, [10, Reference(scalar_symbol),
                                       ArrayType.Extent.DEFERRED,
                                       ArrayType.Extent.ATTRIBUTE])
    array_symbol = DataSymbol("x", array_type)
    reference = Reference(array_symbol)
    # literal value
    (lower_bound, upper_bound, step) = _get_array_bound(reference, 0)
    assert isinstance(lower_bound, Literal)
    assert lower_bound.value == "1"
    assert lower_bound.datatype.intrinsic == ScalarType.Intrinsic.INTEGER
    assert isinstance(upper_bound, Literal)
    assert upper_bound.value == "10"
    assert upper_bound.datatype.intrinsic == ScalarType.Intrinsic.INTEGER
    assert isinstance(step, Literal)
    assert step.value == "1"
    assert step.datatype.intrinsic == ScalarType.Intrinsic.INTEGER
    # Check that the method creates new nodes each time.
    (lower_bound2, upper_bound2, step2) = _get_array_bound(reference, 0)
    assert lower_bound2 is not lower_bound
    assert upper_bound2 is not upper_bound
    assert step2 is not step
    # symbol
    (lower_bound, upper_bound, step) = _get_array_bound(reference, 1)
    assert isinstance(lower_bound, Literal)
    assert lower_bound.value == "1"
    assert lower_bound.datatype.intrinsic == ScalarType.Intrinsic.INTEGER
    assert isinstance(upper_bound, Reference)
    assert upper_bound.symbol.name == "n"
    assert isinstance(step, Literal)
    assert step.value == "1"
    assert step.datatype.intrinsic == ScalarType.Intrinsic.INTEGER
    # Check that the method creates new nodes each time.
    (lower_bound2, upper_bound2, step2) = _get_array_bound(reference, 1)
    assert lower_bound2 is not lower_bound
    assert upper_bound2 is not upper_bound
    assert step2 is not step

    # deferred and attribute
    def _check_ulbound(lower_bound, upper_bound, step, index):
        '''Internal utility routine that checks LBOUND and UBOUND are used
        correctly for the lower and upper array bounds
        respectively.

        '''
        assert isinstance(lower_bound, BinaryOperation)
        assert lower_bound.operator == BinaryOperation.Operator.LBOUND
        assert isinstance(lower_bound.children[0], Reference)
        assert lower_bound.children[0].symbol is array_symbol
        assert isinstance(lower_bound.children[1], Literal)
        assert (lower_bound.children[1].datatype.intrinsic ==
                ScalarType.Intrinsic.INTEGER)
        assert lower_bound.children[1].value == str(index)
        assert isinstance(upper_bound, BinaryOperation)
        assert upper_bound.operator == BinaryOperation.Operator.UBOUND
        assert isinstance(upper_bound.children[0], Reference)
        assert upper_bound.children[0].symbol is array_symbol
        assert isinstance(upper_bound.children[1], Literal)
        assert (upper_bound.children[1].datatype.intrinsic ==
                ScalarType.Intrinsic.INTEGER)
        assert upper_bound.children[1].value == str(index)
        assert isinstance(step, Literal)
        assert step.value == "1"
        assert step.datatype.intrinsic == ScalarType.Intrinsic.INTEGER
    (lower_bound, upper_bound, step) = _get_array_bound(reference, 2)
    _check_ulbound(lower_bound, upper_bound, step, 2)
    (lower_bound2, upper_bound2, step2) = _get_array_bound(reference, 2)
    assert lower_bound2 is not lower_bound
    assert upper_bound2 is not upper_bound
    assert step2 is not step
    (lower_bound, upper_bound, step) = _get_array_bound(reference, 3)
    _check_ulbound(lower_bound, upper_bound, step, 3)
    (lower_bound2, upper_bound2, step2) = _get_array_bound(reference, 3)
    assert lower_bound2 is not lower_bound
    assert upper_bound2 is not upper_bound
    assert step2 is not step


def test_initialise():
    '''Check that the str and name methods work as expected.

    '''
    trans = Matmul2CodeTrans()
    assert (str(trans) == "Convert the PSyIR MATMUL intrinsic to equivalent "
            "PSyIR code.")
    assert trans.name == "Matmul2CodeTrans"


def test_validate1():
    '''Check that the Matmul2Code validate method raises the expected
    exception when the supplied node is the wrong type.

    '''
    trans = Matmul2CodeTrans()
    with pytest.raises(TransformationError) as excinfo:
        trans.validate(None)
    assert ("Error in Matmul2CodeTrans transformation. The supplied node "
            "argument is not a MATMUL operator, found 'NoneType'."
            in str(excinfo.value))


def test_validate2():
    '''Check that the Matmul2Code validate method raises the expected
    exception when the supplied node is a binary operation but not a
    MATMUL.

    '''
    trans = Matmul2CodeTrans()
    with pytest.raises(TransformationError) as excinfo:
        trans.validate(BinaryOperation.create(
            BinaryOperation.Operator.ADD, Literal("1.0", REAL_TYPE),
            Literal("1.0", REAL_TYPE)))
    assert ("Transformation Error: Error in Matmul2CodeTrans transformation. "
            "The supplied node operator is invalid, found 'Operator.ADD'."
            in str(excinfo.value))


def test_validate3():
    '''Check that the Matmul2Code validate method raises the expected
    exception when the supplied node is a MATMUL binary operation but
    doesn't have an assignment as an ancestor.

    '''
    trans = Matmul2CodeTrans()
    vector_type = ArrayType(REAL_TYPE, [10])
    array_type = ArrayType(REAL_TYPE, [10, 10])
    vector = Reference(DataSymbol("x", vector_type))
    array = Reference(DataSymbol("y", array_type))
    matmul = BinaryOperation.create(
        BinaryOperation.Operator.MATMUL, array, vector)
    with pytest.raises(TransformationError) as excinfo:
        trans.validate(matmul)
    assert ("Transformation Error: Error in Matmul2CodeTrans transformation. "
            "This transformation requires the operator to be part of an "
            "assignment statement, but no such assignment was found."
            in str(excinfo.value))


def test_validate4():
    '''Check that the Matmul2Code validate method raises the expected
    exception when the supplied node is a MATMUL binary operation but
    it is not the only operation on the RHS of an assignment.

    '''
    trans = Matmul2CodeTrans()
    vector_type = ArrayType(REAL_TYPE, [10])
    array_type = ArrayType(REAL_TYPE, [10, 10])
    vector = Reference(DataSymbol("x", vector_type))
    array = Reference(DataSymbol("y", array_type))
    matmul = BinaryOperation.create(
        BinaryOperation.Operator.MATMUL, array, vector)
    rhs = BinaryOperation.create(
        BinaryOperation.Operator.MUL, matmul, vector.copy())
    _ = Assignment.create(array.copy(), rhs)
    with pytest.raises(TransformationError) as excinfo:
        trans.validate(matmul)
    assert ("Transformation Error: Matmul2CodeTrans only supports the "
            "transformation of a MATMUL operation when it is the sole "
            "operation on the rhs of an assignment." in str(excinfo.value))


def test_validate5():
    '''Check that the Matmul2Code validate method raises the expected
    exception when the supplied node is a MATMUL binary operation but
    either or both arguments are not references.

    '''
    trans = Matmul2CodeTrans()
    array_type = ArrayType(REAL_TYPE, [10])
    array = ArrayReference.create(DataSymbol("x", array_type),
                                  [Literal("10", INTEGER_TYPE)])
    mult = BinaryOperation.create(
        BinaryOperation.Operator.MUL, array.copy(), array.copy())
    matmul = BinaryOperation.create(
        BinaryOperation.Operator.MATMUL, mult.copy(), mult.copy())
    _ = Assignment.create(array, matmul)
    with pytest.raises(TransformationError) as excinfo:
        trans.validate(matmul)
    assert ("Expected children of a MATMUL BinaryOperation to be references, "
            "but found 'BinaryOperation', 'BinaryOperation'."
            in str(excinfo.value))


def test_validate6():
    '''Check that the Matmul2Code validate method raises the expected
    exception when the supplied node is a MATMUL binary operation but
    either or both of its arguments are references to datasymbols that
    are not arrays.

    '''
    trans = Matmul2CodeTrans()
    scalar = Reference(DataSymbol("x", REAL_TYPE))
    matmul = BinaryOperation.create(
        BinaryOperation.Operator.MATMUL, scalar, scalar.copy())
    _ = Assignment.create(scalar.copy(), matmul)
    with pytest.raises(TransformationError) as excinfo:
        trans.validate(matmul)
    assert ("Transformation Error: Expected children of a MATMUL "
            "BinaryOperation to be references to arrays but found "
            "'DataSymbol', 'DataSymbol' for 'x', 'x'." in str(excinfo.value))


def test_validate_structure_accesses(fortran_reader):
    '''
    Check that the validate() method rejects the case where one or more
    arguments to the MATMUL are structure accesses.

    '''
    psyir = fortran_reader.psyir_from_source(
        "subroutine my_sub()\n"
        "  use my_mod, only: grid_type\n"
        "  type(grid_type) :: grid, grid_inv\n"
        "  real, dimension(5,5) :: result\n"
        "  result = matmul(grid%data, grid_inv%data)\n"
        "end subroutine my_sub\n")
    trans = Matmul2CodeTrans()
    assign = psyir.walk(Assignment)[0]
    with pytest.raises(TransformationError) as err:
        trans.apply(assign.rhs)
    assert ("Expected children of a MATMUL BinaryOperation to be references "
            "to arrays but found 'DataSymbol', 'DataSymbol' for 'grid', "
            "'grid_inv'" in str(err.value))


def test_validate7():
    '''Check that the Matmul2Code validate method raises the expected
    exception when the supplied node is a MATMUL binary operation but
    its first (matrix) argument has fewer than 2 dimensions.

    '''
    trans = Matmul2CodeTrans()
    array_type = ArrayType(REAL_TYPE, [10])
    array = Reference(DataSymbol("x", array_type))
    matmul = BinaryOperation.create(
        BinaryOperation.Operator.MATMUL, array.copy(), array.copy())
    _ = Assignment.create(array, matmul)
    with pytest.raises(TransformationError) as excinfo:
        trans.validate(matmul)
    assert ("Transformation Error: Expected 1st child of a MATMUL "
            "BinaryOperation to be a matrix with at least 2 dimensions, "
            "but found '1'." in str(excinfo.value))


def test_validate8():
    '''Check that the Matmul2Code validate method raises the expected
    exception when the supplied node is a MATMUL binary operation but
    its first (matrix) argument is a reference to a matrix with
    greater than 2 dimensions.

    '''
    trans = Matmul2CodeTrans()
    array_type = ArrayType(REAL_TYPE, [10, 10, 10])
    array = Reference(DataSymbol("x", array_type))
    matmul = BinaryOperation.create(
        BinaryOperation.Operator.MATMUL, array.copy(), array.copy())
    _ = Assignment.create(array, matmul)
    with pytest.raises(TransformationError) as excinfo:
        trans.validate(matmul)
    assert ("Transformation Error: Expected 1st child of a MATMUL "
            "BinaryOperation to have 2 dimensions, but found '3'."
            in str(excinfo.value))


def test_validate9():
    '''Check that the Matmul2Code validate method raises the expected
    exception when the supplied node is a MATMUL binary operation but its
    second argument is a reference to a matrix with more than 2 dimensions.

    '''
    trans = Matmul2CodeTrans()
    array_type = ArrayType(REAL_TYPE, [10, 10])
    array = Reference(DataSymbol("x", array_type))
    vector_type = ArrayType(REAL_TYPE, [10, 10, 10])
    vector = Reference(DataSymbol("y", vector_type))
    matmul = BinaryOperation.create(
        BinaryOperation.Operator.MATMUL, array, vector)
    _ = Assignment.create(array.copy(), matmul)
    with pytest.raises(TransformationError) as excinfo:
        trans.validate(matmul)
    assert ("Transformation Error: Expected 2nd child of a MATMUL "
            "BinaryOperation to have 1 or 2 dimensions, but found '3'."
            in str(excinfo.value))


def test_validate10():
    '''Check that the Matmul2Code validate method raises the expected
    exception when the supplied node is a MATMUL binary operation but
    the first two dimensions of its first argument are not full ranges.

    '''
    trans = Matmul2CodeTrans()
    matmul = create_matmul()
    matrix = matmul.children[0]
    matrix.children[0] = Literal("1", INTEGER_TYPE)
    with pytest.raises(NotImplementedError) as excinfo:
        trans.validate(matmul)
    assert ("To use matmul2code_trans on matmul, the first two indices of the "
            "1st argument 'x' must be full ranges." in str(excinfo.value))


def test_validate11():
    '''Check that the Matmul2Code validate method raises the expected
    exception when the supplied node is a MATMUL binary operation but
    the third (or higher) dimension of the first (matrix) argument is
    indexed via a range.

    '''
    trans = Matmul2CodeTrans()
    matmul = create_matmul()
    matrix = matmul.children[0]
    my_range = matrix.children[0].copy()
    matrix.children[2] = my_range
    with pytest.raises(NotImplementedError) as excinfo:
        trans.validate(matmul)
    assert ("To use matmul2code_trans on matmul, only the first two indices "
            "of the 1st argument are permitted to be Ranges but "
            "found Range at index 2." in str(excinfo.value))


def test_validate12():
    '''Check that the Matmul2Code validate method raises the expected
    exception when the supplied node is a MATMUL binary operation but
    the first dimension of its second (vector) argument is not a full
    range.

    '''
    trans = Matmul2CodeTrans()
    matmul = create_matmul()
    vector = matmul.children[1]
    vector.children[0] = Literal("1", INTEGER_TYPE)
    with pytest.raises(NotImplementedError) as excinfo:
        trans.validate(matmul)
    assert ("To use matmul2code_trans on matmul, the first index of the 2nd "
            "argument 'y' must be a full range." in str(excinfo.value))


def test_validate_2nd_dim_2nd_arg():
    ''' Check that the Matmul2Code validate method raises the expected
    exception when the second dimension of the second argument to MATMUL
    is not a full range. '''
    trans = Matmul2CodeTrans()
    matmul = create_matmul()
    matrix2 = matmul.children[1]
    matrix2.children[1] = Range.create(Literal("1", INTEGER_TYPE),
                                       Literal("2", INTEGER_TYPE))
    with pytest.raises(NotImplementedError) as excinfo:
        trans.validate(matmul)
    assert ("To use matmul2code_trans on matmul for a matrix-matrix "
            "multiplication, the second index of the 2nd argument 'y' must "
            "be a full range." in str(excinfo))


def test_validate13():
    '''Check that the Matmul2Code validate method raises the expected
    exception when the supplied node is a MATMUL binary operation but
    the third (or higher) dimension of the second (vector) argument is
    indexed via a range.

    '''
    trans = Matmul2CodeTrans()
    matmul = create_matmul()
    vector = matmul.children[1]
    my_range = vector.children[0].copy()
    vector.children[2] = my_range
    with pytest.raises(NotImplementedError) as excinfo:
        trans.validate(matmul)
    assert ("To use matmul2code_trans on matmul, only the first two "
            "indices of the 2nd argument are permitted to be a Range but "
            "found Range at index 2." in str(excinfo.value))


def test_validate14():
    '''Check that the Matmul2Code validate method returns without any
    exceptions when the supplied node is a MATMUL binary operation
    that obeys the required rules and constraints.

    '''
    trans = Matmul2CodeTrans()
    matmul = create_matmul()
    trans.validate(matmul)


def test_apply_matvect(tmpdir):
    '''Test that the matmul2code apply method produces the expected
    PSyIR. We use the Fortran backend to help provide the test for
    correctness. This example includes extra indices for the vector
    and matrix arrays with these indices being references.

    '''
    trans = Matmul2CodeTrans()
    matmul = create_matmul()
    root = matmul.root
    trans.apply(matmul)
    writer = FortranWriter()
    result = writer(root)
    assert (
        "subroutine my_kern()\n"
        "  integer, parameter :: idx = 3\n"
        "  real, dimension(5,10,15) :: x\n"
        "  real, dimension(10,20,10) :: y\n"
        "  real, dimension(10) :: result\n"
        "  integer :: i\n"
        "  integer :: j\n"
        "\n"
        "  do i = 1, 5, 1\n"
        "    result(i) = 0.0\n"
        "    do j = 1, 10, 1\n"
        "      result(i) = result(i) + x(i,j,idx) * y(j,idx,1)\n"
        "    enddo\n"
        "  enddo\n"
        "\n"
        "end subroutine my_kern" in result)
    assert Compile(tmpdir).string_compiles(result)


def test_apply_matvect_additional_indices(tmpdir, fortran_writer):
    '''Test that the matmul2code apply method produces the expected
    PSyIR. We use the Fortran backend to help provide the test for
    correctness. This example includes extra indices for the vector
    and matrix arrays with additional indices being literals.

    '''
    trans = Matmul2CodeTrans()
    matmul = create_matmul()
    root = matmul.root
    matmul.children[0].children[2] = Literal("1", INTEGER_TYPE)
    matmul.children[1].children[1] = Literal("2", INTEGER_TYPE)
    trans.apply(matmul)
    result = fortran_writer(root)
    assert (
        "subroutine my_kern()\n"
        "  integer, parameter :: idx = 3\n"
        "  real, dimension(5,10,15) :: x\n"
        "  real, dimension(10,20,10) :: y\n"
        "  real, dimension(10) :: result\n"
        "  integer :: i\n"
        "  integer :: j\n"
        "\n"
        "  do i = 1, 5, 1\n"
        "    result(i) = 0.0\n"
        "    do j = 1, 10, 1\n"
        "      result(i) = result(i) + x(i,j,1) * y(j,2,1)\n"
        "    enddo\n"
        "  enddo\n"
        "\n"
        "end subroutine my_kern" in result)
    assert Compile(tmpdir).string_compiles(result)


def test_apply_matvect_no_indices(tmpdir, fortran_writer):
    '''Test that the matmul2code apply method produces the expected
    PSyIR. We use the Fortran backend to help provide the test for
    correctness. This example includes the array and vector being
    passed with no index information.

    '''
    trans = Matmul2CodeTrans()
    matmul = create_matmul()
    root = matmul.root
    matrix = matmul.children[0]
    lhs_vector = matrix.parent.parent.lhs
    matrix_symbol = matrix.symbol
    matmul.children[0] = Reference(matrix_symbol)
    one = Literal("1", INTEGER_TYPE)
    ten = Literal("10", INTEGER_TYPE)
    twenty = Literal("20", INTEGER_TYPE)
    matrix_symbol.datatype._shape = [
        ArrayType.ArrayBounds(one.copy(), ten.copy()),
        ArrayType.ArrayBounds(one.copy(), twenty.copy())]
    rhs_vector = matmul.children[1]
    rhs_vector_symbol = rhs_vector.symbol
    rhs_vector_symbol.datatype._shape = [ArrayType.ArrayBounds(one.copy(),
                                                               twenty.copy())]
    matmul.children[1] = Reference(rhs_vector_symbol)
    lhs_vector_symbol = lhs_vector.symbol
    lhs_vector_symbol._shape = [ArrayType.ArrayBounds(one.copy(), ten.copy())]
    lhs_vector.replace_with(Reference(lhs_vector_symbol))
    trans.apply(matmul)
    result = fortran_writer(root)
    assert (
        "subroutine my_kern()\n"
        "  integer, parameter :: idx = 3\n"
        "  real, dimension(10,20) :: x\n"
        "  real, dimension(20) :: y\n"
        "  real, dimension(10) :: result\n"
        "  integer :: i\n"
        "  integer :: j\n"
        "\n"
        "  do i = 1, 10, 1\n"
        "    result(i) = 0.0\n"
        "    do j = 1, 20, 1\n"
        "      result(i) = result(i) + x(i,j) * y(j)\n"
        "    enddo\n"
        "  enddo\n"
        "\n"
        "end subroutine my_kern" in result)
    assert Compile(tmpdir).string_compiles(result)


def test_apply_matvect_increment(tmpdir, fortran_writer):
    '''Test that the matmul2code apply method produces the expected
    PSyIR. We use the Fortran backend to help provide the test for
    correctness. This example make the lhs be the same array as the
    second operand of the matmul (the vector in this case).

    '''
    trans = Matmul2CodeTrans()
    one = Literal("1", INTEGER_TYPE)
    five = Literal("5", INTEGER_TYPE)
    matmul = create_matmul()
    root = matmul.root
    assignment = matmul.parent
    vector = assignment.scope.symbol_table.lookup("y")
    assignment.children[0] = ArrayReference.create(
            vector, [Range.create(one, five, one.copy()),
                     one.copy(), one.copy()])
    trans.apply(matmul)
    result = fortran_writer(root)
    assert (
        "subroutine my_kern()\n"
        "  integer, parameter :: idx = 3\n"
        "  real, dimension(5,10,15) :: x\n"
        "  real, dimension(10,20,10) :: y\n"
        "  real, dimension(10) :: result\n"
        "  integer :: i\n"
        "  integer :: j\n"
        "\n"
        "  do i = 1, 5, 1\n"
        "    y(i,1,1) = 0.0\n"
        "    do j = 1, 10, 1\n"
        "      y(i,1,1) = y(i,1,1) + x(i,j,idx) * y(j,idx,1)\n"
        "    enddo\n"
        "  enddo\n"
        "\n"
        "end subroutine my_kern" in result)
    assert Compile(tmpdir).string_compiles(result)


def test_apply_matmat_no_indices(tmpdir, fortran_reader, fortran_writer):
    '''
    Check the apply method works when the second argument to matmul is a
    matrix rather than a vector and no indices are supplied.

    '''
    psyir = fortran_reader.psyir_from_source(
        "subroutine my_sub()\n"
        "  real, dimension(3,6) :: jac\n"
        "  real, dimension(5,3) :: jac_inv\n"
        "  real, dimension(5,6) :: result\n"
        "  result = matmul(jac, jac_inv)\n"
        "end subroutine my_sub\n")
    trans = Matmul2CodeTrans()
    assign = psyir.walk(Assignment)[0]
    trans.apply(assign.rhs)
    out = fortran_writer(psyir)
    assert (
        "subroutine my_sub()\n"
        "  real, dimension(3,6) :: jac\n"
        "  real, dimension(5,3) :: jac_inv\n"
        "  real, dimension(5,6) :: result\n"
        "  integer :: i\n"
        "  integer :: j\n"
        "  integer :: ii\n"
        "\n"
        "  do j = 1, 6, 1\n"
        "    do i = 1, 5, 1\n"
        "      result(i,j) = 0.0\n"
        "      do ii = 1, 3, 1\n"
        "        result(i,j) = result(i,j) + jac(i,ii) * jac_inv(ii,j)\n"
        "      enddo\n"
        "    enddo\n"
        "  enddo\n"
        "\n"
        "end subroutine my_sub" in out)
    assert Compile(tmpdir).string_compiles(out)


def test_apply_matmat_extra_indices(tmpdir, fortran_reader, fortran_writer):
    '''
    Check the apply method works when the second argument to matmul is a
    matrix but additional indices are present.

    '''
    psyir = fortran_reader.psyir_from_source(
        "subroutine my_sub()\n"
        "  real, dimension(3,6,4) :: jac\n"
        "  real, dimension(5,3,4) :: jac_inv\n"
        "  real, dimension(5,6,2) :: result\n"
        "  result(:,:,2) = matmul(jac(:,:,1), jac_inv(:,:,2))\n"
        "end subroutine my_sub\n")
    trans = Matmul2CodeTrans()
    assign = psyir.walk(Assignment)[0]
    trans.apply(assign.rhs)
    out = fortran_writer(psyir)
    assert (
        "  real, dimension(3,6,4) :: jac\n"
        "  real, dimension(5,3,4) :: jac_inv\n"
        "  real, dimension(5,6,2) :: result\n"
        "  integer :: i\n"
        "  integer :: j\n"
        "  integer :: ii\n"
        "\n"
        "  do j = 1, 6, 1\n"
        "    do i = 1, 5, 1\n"
        "      result(i,j,2) = 0.0\n"
        "      do ii = 1, 3, 1\n"
        "        result(i,j,2) = result(i,j,2) + "
        "jac(i,ii,1) * jac_inv(ii,j,2)\n"
        "      enddo\n"
        "    enddo\n"
        "  enddo\n" in out)
    assert Compile(tmpdir).string_compiles(out)


def test_apply_matmat_name_clashes(tmpdir, fortran_reader, fortran_writer):
    '''
    Check the apply method works when there are already symbols present
    with names that would clash with the new loop variables.

    '''
    psyir = fortran_reader.psyir_from_source(
        "subroutine my_sub()\n"
        "  real :: i, j, ii\n"
        "  real, dimension(3,6,4) :: jac\n"
        "  real, dimension(5,3,4) :: jac_inv\n"
        "  real, dimension(5,6,2) :: result\n"
        "  result(:,:,2) = matmul(jac(:,:,1), jac_inv(:,:,2))\n"
        "end subroutine my_sub\n")
    trans = Matmul2CodeTrans()
    assign = psyir.walk(Assignment)[0]
    trans.apply(assign.rhs)
    out = fortran_writer(psyir)
    assert (
        "  real, dimension(3,6,4) :: jac\n"
        "  real, dimension(5,3,4) :: jac_inv\n"
        "  real, dimension(5,6,2) :: result\n"
        "  integer :: i_1\n"
        "  integer :: j_1\n"
        "  integer :: ii_1\n"
        "\n"
        "  do j_1 = 1, 6, 1\n"
        "    do i_1 = 1, 5, 1\n"
        "      result(i_1,j_1,2) = 0.0\n"
        "      do ii_1 = 1, 3, 1\n"
        "        result(i_1,j_1,2) = result(i_1,j_1,2) + "
        "jac(i_1,ii_1,1) * jac_inv(ii_1,j_1,2)\n"
        "      enddo\n"
        "    enddo\n"
        "  enddo\n" in out)
    assert Compile(tmpdir).string_compiles(out)
