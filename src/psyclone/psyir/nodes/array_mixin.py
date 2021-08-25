# -----------------------------------------------------------------------------
# BSD 3-Clause License
#
# Copyright (c) 2021, Science and Technology Facilities Council.
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
# Authors R. W. Ford, A. R. Porter and S. Siso, STFC Daresbury Lab
#         I. Kavcic, Met Office
#         J. Henrichs, Bureau of Meteorology
# -----------------------------------------------------------------------------

''' This module contains the implementation of the abstract ArrayMixin. '''

from __future__ import absolute_import

import abc
import six

from psyclone.errors import InternalError
from psyclone.psyir.nodes.datanode import DataNode
from psyclone.psyir.nodes.literal import Literal
from psyclone.psyir.nodes.operation import BinaryOperation
from psyclone.psyir.nodes.ranges import Range
from psyclone.psyir.nodes.reference import Reference
from psyclone.psyir.symbols.datatypes import ScalarType


@six.add_metaclass(abc.ABCMeta)
class ArrayMixin(object):
    '''
    Abstract class used to add functionality common to Nodes that represent
    Array accesses.

    '''
    @staticmethod
    def _validate_child(position, child):
        '''
        :param int position: the position to be validated.
        :param child: a child to be validated.
        :type child: :py:class:`psyclone.psyir.nodes.Node`

        :return: whether the given child and position are valid for this node.
        :rtype: bool

        '''
        # pylint: disable=unused-argument
        return isinstance(child, (DataNode, Range))

    def get_signature_and_indices(self):
        '''
        Constructs the Signature of this array access and a list of the
        indices used.

        :returns: the Signature of this array reference, and \
            a list of the indices used for each component (empty list \
            if an access is not an array). In this base class there is \
            no other component, so it just returns a list with a list \
            of all indices.
        :rtype: tuple(:py:class:`psyclone.core.Signature`, list of \
            lists of indices)
        '''
        sig, _ = super(ArrayMixin, self).get_signature_and_indices()
        return (sig, [self.indices[:]])

    def _validate_index(self, index):
        '''Utility function that checks that the supplied index is an integer
        and is less than the number of array dimensions.

        :param int index: the array index to check.

        :raises TypeError: if the index argument is not an integer.
        :raises ValueError: if the index value is greater than the \
            number of dimensions in the array (-1).

        '''
        if not isinstance(index, int):
            raise TypeError(
                "The index argument should be an integer but found '{0}'."
                "".format(type(index).__name__))
        if index > len(self.indices)-1:
            raise ValueError(
                "In ArrayReference '{0}' the specified index '{1}' must be "
                "less than the number of dimensions '{2}'."
                "".format(self.name, index, len(self.indices)))

    def is_lower_bound(self, index):
        '''Returns True if the specified array index contains a Range node
        which has a starting value given by the 'LBOUND(name,index)'
        intrinsic where 'name' is the name of the current Array and
        'index' matches the specified array index. Otherwise False is
        returned.

        For example, if a Fortran array A was declared as
        A(10) then the starting value is 1 and LBOUND(A,1) would
        return that value.

        :param int index: the array index to check.

        :returns: True if the array index is a range with its start \
            value being LBOUND(array,index) and False otherwise.
        :rtype: bool

        '''
        self._validate_index(index)

        array_dimension = self.indices[index]
        if not isinstance(array_dimension, Range):
            return False

        lower = array_dimension.start
        if not (isinstance(lower, BinaryOperation) and
                lower.operator == BinaryOperation.Operator.LBOUND):
            return False

        if not isinstance(lower.children[0], Reference):
            return False

        if not self._matching_access(lower.children[0]):
            return False

        if not (isinstance(lower.children[1], Literal) and
                lower.children[1].datatype.intrinsic ==
                ScalarType.Intrinsic.INTEGER
                and lower.children[1].value == str(index+1)):
            return False
        return True

    def is_upper_bound(self, index):
        '''Returns True if the specified array index contains a Range node
        which has a stopping value given by the 'UBOUND(name,index)'
        intrinsic where 'name' is the name of the current ArrayReference and
        'index' matches the specified array index. Otherwise False is
        returned.

        For example, if a Fortran array A was declared as
        A(10) then the stopping value is 10 and UBOUND(A,1) would
        return that value.

        :param int index: the array index to check.

        :returns: True if the array index is a range with its stop \
            value being UBOUND(array,index) and False otherwise.
        :rtype: bool

        '''
        self._validate_index(index)

        array_dimension = self.indices[index]
        if not isinstance(array_dimension, Range):
            return False

        upper = array_dimension.stop
        if not (isinstance(upper, BinaryOperation) and
                upper.operator == BinaryOperation.Operator.UBOUND):
            return False

        if not isinstance(upper.children[0], Reference):
            return False

        if not self._matching_access(upper.children[0]):
            return False

        if not (isinstance(upper.children[1], Literal) and
                upper.children[1].datatype.intrinsic ==
                ScalarType.Intrinsic.INTEGER
                and upper.children[1].value == str(index+1)):
            return False
        return True

    def _matching_access(self, node):
        '''
        Examines the full structure access represented by the supplied node
        to see whether it is the same as the one for this node. Any indices
        on the innermost member access are ignored. e.g.
        A(3)%B%C(1) will match with A(3)%B%C but not with A(2)%B%C(1)

        :returns: True if the structure accesses match, False otherwise.
        :rtype: bool

        '''
        if isinstance(self, Reference):
            if not isinstance(node, Reference):
                return False
            # This node is a reference so just compare symbol names.
            return self.symbol.name == node.symbol.name

        # This node is somewhere within a structure access so we need to
        # get the parent Reference and keep a record of how deep this node
        # is within the structure access. e.g. if this node was the
        # StructureMember 'b' in a%c%b%d then its depth would be 2.
        current = self
        depth = 1
        while current.parent and not isinstance(current.parent, Reference):
            depth += 1
            current = current.parent
        parent_ref = current.parent
        if not parent_ref:
            return False

        # Now we have the parent Reference and the depth, we can construct the
        # Signatures and compare them to the required depth.
        self_sig, self_indices = parent_ref.get_signature_and_indices()
        node_sig, node_indices = node.get_signature_and_indices()
        if self_sig[:depth+1] != node_sig[:depth+1]:
            return False

        # We use the FortranWriter to simplify the job of comparing array-index
        # expressions but have to import it here to avoid circular dependencies
        # pylint: disable=import-outside-toplevel
        from psyclone.psyir.backend.fortran import FortranWriter
        fwriter = FortranWriter()

        # Examine the indices, ignoring any on the innermost accesses (hence
        # the slice to `depth` rather than `depth + 1` below).
        for indices in zip(self_indices[:depth], node_indices[:depth]):
            if ("".join(fwriter(idx) for idx in indices[0]) !=
                    "".join(fwriter(idx) for idx in indices[1])):
                return False
        return True

    def is_full_range(self, index):
        '''Returns True if the specified array index is a Range Node that
        specifies all elements in this index. In the PSyIR this is
        specified by using LBOUND(name,index) for the lower bound of
        the range, UBOUND(name,index) for the upper bound of the range
        and "1" for the range step.

        :param int index: the array index to check.

        :returns: True if the access to this array index is a range \
            that specifies all index elements. Otherwise returns \
            False.
        :rtype: bool

        '''
        self._validate_index(index)

        array_dimension = self.indices[index]
        if isinstance(array_dimension, Range):
            if self.is_lower_bound(index) and self.is_upper_bound(index):
                step = array_dimension.children[2]
                if (isinstance(step, Literal) and
                        step.datatype.intrinsic == ScalarType.Intrinsic.INTEGER
                        and str(step.value) == "1"):
                    return True
        return False

    @property
    def indices(self):
        '''
        Supports semantic-navigation by returning the list of nodes
        representing the index expressions for this array reference.

        :returns: the PSyIR nodes representing the array-index expressions.
        :rtype: list of :py:class:`psyclone.psyir.nodes.Node`

        :raises InternalError: if this node has no children or if they are \
                               not valid array-index expressions.

        '''
        if not self._children:
            raise InternalError(
                "{0} malformed or incomplete: must have one or more "
                "children representing array-index expressions but found "
                "none.".format(type(self).__name__))
        for idx, child in enumerate(self._children):
            if not self._validate_child(idx, child):
                raise InternalError(
                    "{0} malformed or incomplete: child {1} must by a psyir."
                    "nodes.DataNode or Range representing an array-index "
                    "expression but found '{2}'".format(
                        type(self).__name__, idx, type(child).__name__))
        return self.children


# For AutoAPI documentation generation
__all__ = ['ArrayMixin']