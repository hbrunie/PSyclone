# -----------------------------------------------------------------------------
# BSD 3-Clause License
#
# Copyright (c) 2021-2022, Science and Technology Facilities Council.
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
# Author J. Henrichs, Bureau of Meteorology
# Modified: R. W. Ford, STFC Daresbury Lab
# -----------------------------------------------------------------------------

''' This module provides access to sympy-based symbolic maths
functions.'''


from sympy import Complexes, core, expand, simplify, solveset


class SymbolicMaths:
    '''A wrapper around the symbolic maths package 'sympy'. It
    provides convenience functions for PSyclone. It has a Singleton
    access, e.g.:

    >>> from psyclone.psyir.backend.fortran import FortranWriter
    >>> from psyclone.core import SymbolicMaths
    >>> sympy = SymbolicMaths.get()
    >>> # Assume lhs is the PSyIR of 'i+j', and rhs is 'j+i'
    >>> if sympy.equal(lhs, rhs):
    ...     writer = FortranWriter()
    ...     print("'{0}' and '{1}' are equal."
    ...           .format(writer(lhs), writer(rhs)))
    'i + j' and 'j + i' are equal.

    '''
    # Keeps track if importing sympy has been tried.
    _has_been_imported = False

    # Class variable to store the SymbolicMaths instance if sympy is
    # available, or None otherwise.
    _instance = None

    # -------------------------------------------------------------------------
    @staticmethod
    def get():
        '''Static function that creates (if necessary) and returns the
        singleton SymbolicMaths instance.

        :returns: the instance of the symbolic maths class.
        :rtype: :py:class:`psyclone.core.SymbolicMaths.`

        '''
        if SymbolicMaths._instance is None:
            SymbolicMaths._instance = SymbolicMaths()

        return SymbolicMaths._instance

    # -------------------------------------------------------------------------
    @staticmethod
    def equal(exp1, exp2):
        '''Test if the two PSyIR operations are identical. This is
        done by converting the operations to the equivalent Fortran
        representation, which can be fed into sympy for evaluation.

        :param exp1: the first expression to be compared.
        :type exp1: py:class:`psyclone.psyir.nodes.Node` or None
        :param exp2: the first expression to be compared.
        :type exp2: py:class:`psyclone.psyir.nodes.Node` or None

        :returns: whether the two expressions are mathematically \
            identical.
        :rtype: bool

        '''
        # Some tests provide a None as parameters
        if exp1 is None or exp2 is None:
            return exp1 == exp2

        return SymbolicMaths.subtract(exp1, exp2) == 0

    # -------------------------------------------------------------------------
    @staticmethod
    def never_equal(exp1, exp2):
        '''Returns if the given SymPy expressions are always different,
        without assuming any values for variables. E.g. `n-1` and `n` are
        always different, but `5` and `n` are not always different.

        :param exp1: the first expression to be compared.
        :type exp1: py:class:`psyclone.psyir.nodes.Node`
        :param exp2: the first expression to be compared.
        :type exp2: py:class:`psyclone.psyir.nodes.Node`

        :returns: whether or not the expressions are never equal.
        :rtype: bool

        '''
        result = SymbolicMaths.subtract(exp1, exp2)

        # If the result is 0, they are always the same:
        if isinstance(result, core.numbers.Zero):
            return False

        # If the result is an integer value, the result is independent
        # of any variable, and never equal
        if isinstance(result, core.numbers.Integer):
            return result != 0

        # Otherwise the result depends on one or more variables (e.g.
        # n-5), so it might be zero.
        return False

    # -------------------------------------------------------------------------
    @staticmethod
    def subtract(exp1, exp2):
        '''Subtracts two PSyIR operations. This is done by converting the
        operations to the equivalent Fortran representation, which can be fed
        into sympy for evaluation.

        :param exp1: the first expression to be compared.
        :type exp1: py:class:`psyclone.psyir.nodes.Node` or None
        :param exp2: the first expression to be compared.
        :type exp2: py:class:`psyclone.psyir.nodes.Node` or None

        :returns: the sympy expression resulting from subtracting exp2 \
            from exp1.
        :rtype: a SymPy object

        '''

        # Avoid circular import
        # pylint: disable=import-outside-toplevel
        from psyclone.psyir.backend.sympy_writer import SymPyWriter

        # Use the SymPyWriter to convert the two expressions to
        # SymPy expressions:
        sympy_expressions = SymPyWriter.convert_to_sympy_expressions([exp1,
                                                                      exp2])
        # Simplify triggers a set of SymPy algorithms to simplify
        # the expression.
        return simplify(sympy_expressions[0] - sympy_expressions[1])

    # -------------------------------------------------------------------------
    @staticmethod
    def solve_equal_for(exp1, exp2, symbol):
        '''Returns all solutions of exp1==exp2, solved for
        the specified symbol. It restricts the solution domain to integer
        values. If there is an infinite number of solutions, it returns
        the string 'independent', indicating that the solution of exp1==exp2
        does not depend on the specified symbol. This is done to avoid that
        the SymPy instance representing an infinite set is used elsewhere
        in PSyclone (i.e. creating a dependency in other modules to SymPy).
        The FiniteSet returned otherwise is compatible witha Python set
        and so does not introduce any dependencies.

        :param exp1: the first expression.
        :type exp1: a SymPy expressio.
        :param exp2: the second expression.
        :type exp2: a SymPy expressio.
        :param symbol: the symbol for which to solve.
        :type exp2: a SymPy Symbol

        :returns: a set of solutions, or "independent".
        :rtype: a SymPy.FiniteSet of solutions, or "str"

        '''
        # We could restrict the domain to Integers, but in case of
        # general solutions (x=i+1 or so), we get an intersection as
        # as result, which is then difficult to handle. It's actually
        # easier to not restrict the domain, and detect and interpret
        # a non-integer solution later.
        solution = solveset(exp1-exp2, symbol)
        if solution == Complexes:
            # The solution is actually independent of the symbol
            # Return a string (instead of the SymPy specific set
            # instance, which would introduce dependencies on
            # SymPy to other files).
            return "independent"

        return solution

    # -------------------------------------------------------------------------
    @staticmethod
    def expand(expr):
        '''Expand a PSyIR expression. This is done by converting the PSyIR
        expression to a sympy expression, applying the expansion
        operation and then converting the resultant output back into
        PSyIR.

        Currently does not work if the PSyIR expression contains Range
        nodes, see issue #1655.

        :param expr: the expression to be expanded.
        :type expr: py:class:`psyclone.psyir.nodes.Node`

        '''
        # Avoid circular import
        # pylint: disable=import-outside-toplevel
        from psyclone.psyir.backend.sympy_writer import SymPyWriter
        from psyclone.psyir.frontend.fortran import FortranReader
        from psyclone.psyir.nodes import Reference, Literal, Routine

        # variables and literals do not require expansion
        if isinstance(expr, (Reference, Literal)):
            return
        # Convert the PSyIR expression to a sympy expression
        sympy_expression = SymPyWriter.convert_to_sympy_expressions([expr])
        # Expand the expression
        result = expand(sympy_expression[0])
        # If the expanded result is the same as the original then
        # nothing needs to be done.
        if result == sympy_expression[0]:
            return
        # Find the required symbol table in the original PSyIR
        symbol_table = expr.ancestor(Routine).symbol_table
        # Convert the new sympy expression to PSyIR
        reader = FortranReader()
        new_expr = reader.psyir_from_expression(str(result), symbol_table)
        # Replace the old PSyIR expression with the new expanded PSyIR
        # expression
        expr.replace_with(new_expr)
