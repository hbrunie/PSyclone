# -----------------------------------------------------------------------------
# BSD 3-Clause License
#
# Copyright (c) 2022, Science and Technology Facilities Council.
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
# Author: J. Henrichs, Bureau of Meteorology

'''Module providing a transformation that removed induction variables from
a loop. '''

from __future__ import absolute_import

from psyclone.core import AccessType, VariablesAccessInfo
from psyclone.psyGen import Transformation
from psyclone.psyir.nodes import (ArrayReference, Assignment, BinaryOperation,
                                  Loop, Reference)
from psyclone.psyir.transformations.transformation_error \
    import TransformationError


class ReplaceInductionVariables(Transformation):
    '''Move all supported induction variables out of the loop, and replace
    their usage inside the loop. For example:

    >>> from psyclone.psyir.frontend.fortran import FortranReader
    >>> from psyclone.psyir.nodes import Loop
    >>> from psyclone.psyir.transformations import ReplaceInductionVariables
    >>> from psyclone.psyir.backend.fortran import FortranWriter
    >>> psyir = FortranReader().psyir_from_source("""
    ... subroutine sub()
    ...     integer :: i, im, ic, tmp(100)
    ...     do i=1, 100
    ...         im = i - 1
    ...         ic = 2
    ...         tmp(i) = ic * im
    ...     enddo
    ... end subroutine sub""")
    >>> loop = psyir.walk(Loop)[0]
    >>> ReplaceInductionVariables().apply(loop)
    >>> print(FortranWriter()(psyir))

    will generate:

    .. code-block:: fortran

        subroutine sub()
          integer :: i
          integer :: im
          integer :: ic
          integer, dimension(100) :: tmp

          do i = 1, 100, 1
            tmp(i) = 2 * (i - 1)
          enddo
          ic = 2
          im = i - 1 - 1

        end subroutine sub

    After the loop the replaced assignments to the induction variables are
    added so these variables will have the correct value if they should be
    used elsewhere.

    The following restrictions apply for the assignment to an induction
    variable:

    * the variable must be a non-structure scalar.
    * none of variables on the right-hand side can be written in the loop body
      (the loop variable is written in the Loop statement, not in
      the body, so it can be used).
    * the assigned variable must not be read before the assignment.
    * the assigned variable cannot occur on the right-hand side
      (e.g. `k = k + 3`).
    * there must only be one assignment to the variable.

    '''
    def __str__(self):
        return "Replaces all induction variables in a loop."

    # ------------------------------------------------------------------------
    @staticmethod
    def _replace_references(psyir, original, replacement):
        '''This function replaces all occurrences of the `original` reference
        with a copy of the node of the `replacement` in the given PSyIR tree.

        :param psyir: the PSyIR in which to replace `original` with \
            `replacement`.
        :type psyir: :py:class:`psyclone.psyir.nodes.Node`
        :param original: the reference which is to be replaced.
        :type original: :py:class:`psyclone.psyir.nodes.Reference`
        :param replacement: the node to insert.
        :type replacement: :py:class:`psyclone.psyir.nodes.Node`

        '''
        # Just in case we avoid modifying the tree while walking it,
        # so first just store the nodes to be replaced in a list
        to_replace = []
        for node in psyir.walk(Reference):
            if node == original:
                to_replace.append(node)

        # Then do the actual replacement
        for node in to_replace:
            copy = replacement.copy()
            node.replace_with(copy)

    # ------------------------------------------------------------------------
    @staticmethod
    def _is_induction_variable(assignment, accesses_in_loop_body):
        '''Tests if the assignment is an induction statement that can be
        replaced. An induction statements requires:
        - None of the variables on the rhs can be written in the loop body
          (the loop variable is written in the Loop statement, not in
          the body)
        - the assigned variable cannot be read before the assignment
        - there must only be one assignment to the variable

        :param assignment: the assignment statement to be tested, which \
            must not be an array variable.
        :type assignment: :py:class:`psyclone.psyir.nodes.Assignment`
        :param accesses_in_loop_body: the access information for all \
            variables in the loop body.
        :type accesses_in_loop_body: \
            :py:class:`psyclone.core.VariablesAccessInfo`

        :returns: whether the assignment is an induction statement that \
            can be replaced.
        :rtype: bool

        '''
        # Collect all variables used on the rhs of assignment:
        rhs_accesses = VariablesAccessInfo(assignment.rhs)
        # If the rhs uses any variable that is written in the loop body, this
        # is not a (simple) induction variable and cannot be replaced.
        # Note that the write to the loop variable is part of the Loop
        # statement, and is therefore not included in accesses_in_loop_body.
        # This statement will also catch assignments like 'k=k+3' (which
        # could be support in some cases):
        if any(not accesses_in_loop_body[sig].is_read_only()
               for sig in rhs_accesses):
            return False

        # Test that this assignment is the first access to this variable
        # in the body. Get the signature from the node (ignore indices)
        sig = assignment.lhs.get_signature_and_indices()[0]
        var_accesses = accesses_in_loop_body[sig]
        if var_accesses[0].node is not assignment.lhs:
            return False

        # Check if there is another write to this variable
        # after the first one:
        if any(access.access_type != AccessType.READ
               for access in var_accesses.all_accesses[1:]):
            return False

        return True

    # ------------------------------------------------------------------------
    def apply(self, node, options=None):
        '''Apply the ReplaceInductionVariables transformation to the
        specified node. The node must be a loop. In case of nested
        loops, the transformation might need to be applied several
        time, from the inner-most loop outwards.

        :param node: a Loop node.
        :type node: :py:class:`psyclone.psyir.nodes.Loop`

        '''
        self.validate(node)
        loop_var = node.variable.name

        # Find assignments that are directly part of the loop (this avoid
        # issues with assignment inside if statements):
        all_accesses = VariablesAccessInfo(node.loop_body)
        indx = 0
        while indx < len(node.loop_body.children):
            assignment = node.loop_body.children[indx]
            # Only handle assignments, ignore if statements etc
            if not isinstance(assignment, Assignment):
                indx += 1
                continue

            # Assignment to arrays are ignored as well:
            if isinstance(assignment.lhs, ArrayReference):
                indx += 1
                continue

            if not self._is_induction_variable(assignment, all_accesses):
                indx += 1
                continue

            # This assignment is an induction variable and can be replaced:
            # Remove it from the loop body, and then replace all References
            # to this variable (i.e. assignment.lhs) in the body with the
            # RHS of the assignment:
            assignment.detach()
            self._replace_references(node, assignment.lhs, assignment.rhs)

            # In case that the variable value is used after the loop, we add
            # an assignment to this variable after the loop, which gives it
            # the expected value. The final value of the value of the loop
            # variable minus the step size.
            symbol_table = node.scope.symbol_table
            loop_var_symbol = symbol_table.lookup(loop_var)
            # Create the expression `loop_var - step`:
            final = BinaryOperation.create(BinaryOperation.Operator.SUB,
                                           Reference(loop_var_symbol),
                                           node.step_expr.copy())
            # And add the assignment back to the end of the loop, replacing
            # the loop variable with the final value:
            self._replace_references(assignment, Reference(loop_var_symbol),
                                     final)
            # Now attach the assignment after the loop, in case
            # that this value is needed elsewhere.
            node.parent.children.insert(node.position+1, assignment)

            # Recompute the accesses in the body, which was modified
            all_accesses = VariablesAccessInfo(node.loop_body)

            # Since the assignment is removed now, we do not need to
            # increment 'indx' here, which will now point to the next
            # statement in the body.

    # ------------------------------------------------------------------------
    def validate(self, node, options=None):
        '''Perform various checks to ensure that it is valid to apply the
        ReplaceInductionVariables transformation to the supplied PSyIR Node.

        :param node: the node that is being checked.
        :type node: :py:class:`psyclone.psyir.nodes.Assignment`

        :raises TransformationError: if the node argument is not a \
            Loop.

        '''
        if not isinstance(node, Loop):
            raise TransformationError(
                f"Error in {self.name} transformation. The supplied node "
                f"argument should be a PSyIR Loop, but found "
                f"'{type(node).__name__}'.")


__all__ = [
    'ReplaceInductionVariables']
