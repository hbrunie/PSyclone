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
# Authors R. W. Ford, A. R. Porter and S. Siso, STFC Daresbury Lab
#         A. B. G. Chalk, STFC Daresbury Lab
#         I. Kavcic,    Met Office
#         C.M. Maynard, Met Office / University of Reading
#         J. Henrichs, Bureau of Meteorology
# -----------------------------------------------------------------------------

''' This module contains the implementation of the various OpenMP Directive
nodes.'''


from __future__ import absolute_import
import abc
import six

from psyclone.configuration import Config
from psyclone.core import AccessType, VariablesAccessInfo
from psyclone.errors import GenerationError, InternalError
from psyclone.f2pygen import (AssignGen, UseGen, DeclGen, DirectiveGen,
                              CommentGen)
from psyclone.psyir.nodes import Reference, Assignment, IfBlock, Loop, \
                                 ArrayReference, ArrayOfStructuresReference, \
                                 StructureReference, Literal
from psyclone.psyir.nodes.operation import BinaryOperation
from psyclone.psyir.nodes.directive import StandaloneDirective, \
    RegionDirective
from psyclone.psyir.nodes.loop import Loop
from psyclone.psyir.nodes.literal import Literal
from psyclone.psyir.nodes.routine import Routine
from psyclone.psyir.nodes.omp_clauses import OMPGrainsizeClause, \
    OMPNowaitClause, OMPNogroupClause, OMPNumTasksClause
from psyclone.psyir.nodes.schedule import Schedule
from psyclone.psyir.symbols import INTEGER_TYPE

# OMP_OPERATOR_MAPPING is used to determine the operator to use in the
# reduction clause of an OpenMP directive.
OMP_OPERATOR_MAPPING = {AccessType.SUM: "+"}


class OMPDirective(metaclass=abc.ABCMeta):
    '''
    Base mixin class for all OpenMP-related directives.

    This class is useful to provide a unique common ancestor to all the
    OpenMP directives, for instance when traversing the tree with
    `node.walk(OMPDirective)`

    Note that classes inheriting from it must place the OMPDirective in
    front of the other Directive node sub-class, so that the Python
    MRO gives preference to this class's attributes.
    '''
    _PREFIX = "OMP"


@six.add_metaclass(abc.ABCMeta)
class OMPRegionDirective(OMPDirective, RegionDirective):
    '''
    Base class for all OpenMP region-related directives.

    '''
    def _get_reductions_list(self, reduction_type):
        '''
        Returns the names of all scalars within this region that require a
        reduction of type 'reduction_type'. Returned names will be unique.

        :param reduction_type: the reduction type (e.g. AccessType.SUM) to \
                               search for.
        :type reduction_type: :py:class:`psyclone.core.access_type.AccessType`

        :returns: names of scalar arguments with reduction access.
        :rtype: list of str

        '''
        result = []
        const = Config.get().api_conf().get_constants()
        for call in self.kernels():
            if not call.arguments:
                continue
            for arg in call.arguments.args:
                if arg.argument_type in const.VALID_SCALAR_NAMES:
                    if arg.descriptor.access == reduction_type:
                        if arg.name not in result:
                            result.append(arg.name)
        return result


@six.add_metaclass(abc.ABCMeta)
class OMPStandaloneDirective(OMPDirective, StandaloneDirective):
    '''
    Base class for all OpenMP-related standalone directives

    '''


class OMPDeclareTargetDirective(OMPStandaloneDirective):
    '''
    Class representing an OpenMP Declare Target directive in the PSyIR.

    '''
    def gen_code(self, parent):
        '''Generate the fortran OMP Declare Target Directive and any
        associated code.

        :param parent: the parent Node in the Schedule to which to add our \
                       content.
        :type parent: sub-class of :py:class:`psyclone.f2pygen.BaseGen`
        '''
        # Check the constraints are correct
        self.validate_global_constraints()

        # Generate the code for this Directive
        parent.add(DirectiveGen(parent, "omp", "begin", "declare", "target"))

    def begin_string(self):
        '''Returns the beginning statement of this directive, i.e.
        "omp routine". The visitor is responsible for adding the
        correct directive beginning (e.g. "!$").

        :returns: the opening statement of this directive.
        :rtype: str

        '''
        # pylint: disable=no-self-use
        return "omp declare target"

    def validate_global_constraints(self):
        '''
        Perform validation checks that can only be done at code-generation
        time.

        :raises GenerationError: if this directive is not the first statement \
            in a routine.

        '''
        if self.parent and (not isinstance(self.parent, Routine) or
                            self.parent.children[0] is not self):
            raise GenerationError(
                f"A OMPDeclareTargetDirective must be the first child (index "
                f"0) of a Routine but found one as child {self.position} of a "
                f"{type(self.parent).__name__}.")

        super().validate_global_constraints()


class OMPTaskwaitDirective(OMPStandaloneDirective):
    '''
    Class representing an OpenMP TASKWAIT directive in the PSyIR.

    '''
    def validate_global_constraints(self):
        '''
        Perform validation checks that can only be done at code-generation
        time.

        :raises GenerationError: if this OMPTaskwait is not enclosed \
                            within some OpenMP parallel region.

        '''
        # It is only at the point of code generation that we can check for
        # correctness (given that we don't mandate the order that a user
        # can apply transformations to the code). As a Parallel Child
        # directive, we must have an OMPParallelDirective as an ancestor
        # somewhere back up the tree.
        if not self.ancestor(OMPParallelDirective,
                             excluding=OMPParallelDoDirective):
            raise GenerationError(
                "OMPTaskwaitDirective must be inside an OMP parallel region "
                "but could not find an ancestor OMPParallelDirective node")

        super(OMPTaskwaitDirective, self).validate_global_constraints()

    def gen_code(self, parent):
        '''Generate the fortran OMP Taskwait Directive and any associated
        code

        :param parent: the parent Node in the Schedule to which to add our \
                       content.
        :type parent: sub-class of :py:class:`psyclone.f2pygen.BaseGen`
        '''
        # Check the constraints are correct
        self.validate_global_constraints()

        # Generate the code for this Directive
        parent.add(DirectiveGen(parent, "omp", "begin", "taskwait", ""))
        # No children or end code for this node

    def begin_string(self):
        '''Returns the beginning statement of this directive, i.e.
        "omp taskwait". The visitor is responsible for adding the
        correct directive beginning (e.g. "!$").

        :returns: the opening statement of this directive.
        :rtype: str

        '''
        # pylint: disable=no-self-use
        return "omp taskwait"


@six.add_metaclass(abc.ABCMeta)
class OMPSerialDirective(OMPRegionDirective):
    '''
    Abstract class representing OpenMP serial regions, e.g.
    OpenMP SINGLE or OpenMP Master.

    '''

    def validate_global_constraints(self):
        '''
        Perform validation checks that can only be done at code-generation
        time.

        :raises GenerationError: if this OMPSerial is not enclosed \
                                 within some OpenMP parallel region.
        :raises GenerationError: if this OMPSerial is enclosed within \
                                 any OMPSerialDirective subclass region.

        '''
        # It is only at the point of code generation that we can check for
        # correctness (given that we don't mandate the order that a user
        # can apply transformations to the code). As a Parallel Child
        # directive, we must have an OMPParallelDirective as an ancestor
        # somewhere back up the tree.
        # Also check the single region is not enclosed within another OpenMP
        # single region.
        # It could in principle be allowed for that parent to be a ParallelDo
        # directive, however I can't think of a use case that would be done
        # best in a parallel code by that pattern
        if not self.ancestor(OMPParallelDirective,
                             excluding=OMPParallelDoDirective):
            raise GenerationError(
                "{} must be inside an OMP parallel region but "
                "could not find an ancestor OMPParallelDirective node".format(
                    self._text_name))

        if self.ancestor(OMPSerialDirective):
            raise GenerationError(
                    "{} must not be inside another OpenMP "
                    "serial region".format(self._text_name))

        super(OMPSerialDirective, self).validate_global_constraints()


class OMPSingleDirective(OMPSerialDirective):
    '''
    Class representing an OpenMP SINGLE directive in the PSyIR.

    :param list children: List of Nodes that are children of this Node.
    :param parent: The Node in the AST that has this directive as a child.
    :type parent: :py:class:`psyclone.psyir.nodes.Node`
    :param bool nowait: Argument describing whether this single should have \
        a nowait clause applied. Default value is False.

    '''
    _children_valid_format = "Schedule, [OMPNowaitClause]"
    # Textual description of the node
    _text_name = "OMPSingleDirective"

    def __init__(self, children=None, parent=None, nowait=False):

        self._nowait = nowait
        # Call the init method of the base class once we've stored
        # the nowait requirement
        super(OMPSingleDirective, self).__init__(children=children,
                                                 parent=parent)
        if self._nowait:
            self.children.append(OMPNowaitClause())

    @staticmethod
    def _validate_child(position, child):
        '''
         Decides whether a given child and position are valid for this node.
         The rules are:
         1. Child 0 must always be a Schedule.
         2. Child 1 can only be a OMPNowaitClause.

        :param int position: the position to be validated.
        :param child: a child to be validated.
        :type child: :py:class:`psyclone.psyir.nodes.Node`

        :return: whether the given child and position are valid for this node.
        :rtype: bool

        '''
        if position == 0:
            return isinstance(child, Schedule)
        if position == 1:
            return isinstance(child, OMPNowaitClause)
        return False

    @property
    def nowait(self):
        '''
        :returns: whether the nowait clause is specified for this directive.
        :rtype: bool

        '''
        return self._nowait

    def gen_code(self, parent):
        '''Generate the fortran OMP Single Directive and any associated
        code

        :param parent: the parent Node in the Schedule to which to add our \
                       content.
        :type parent: sub-class of :py:class:`psyclone.f2pygen.BaseGen`
        '''
        # Check the constraints are correct
        self.validate_global_constraints()

        # Capture the nowait section of the string if required
        nowait_string = ""
        if self._nowait:
            nowait_string = "nowait"

        parent.add(DirectiveGen(parent, "omp", "begin", "single",
                                nowait_string))

        # Generate the code for all of this node's children
        for child in self.dir_body:
            child.gen_code(parent)

        # Generate the end code for this node
        parent.add(DirectiveGen(parent, "omp", "end", "single", ""))

    def begin_string(self):
        '''Returns the beginning statement of this directive, i.e.
        "omp single". The visitor is responsible for adding the
        correct directive beginning (e.g. "!$").

        :returns: the opening statement of this directive.
        :rtype: str

        '''
        # pylint: disable=no-self-use
        return "omp single"

    def end_string(self):
        '''Returns the end (or closing) statement of this directive, i.e.
        "omp end single". The visitor is responsible for adding the
        correct directive beginning (e.g. "!$").

        :returns: the end statement for this directive.
        :rtype: str

        '''
        # pylint: disable=no-self-use
        return "omp end single"


class OMPMasterDirective(OMPSerialDirective):
    '''
    Class representing an OpenMP MASTER directive in the PSyclone AST.

    '''

    # Textual description of the node
    _text_name = "OMPMasterDirective"

    def gen_code(self, parent):
        '''Generate the Fortran OMP Master Directive and any associated
        code

        :param parent: the parent Node in the Schedule to which to add our \
                       content.
        :type parent: sub-class of :py:class:`psyclone.f2pygen.BaseGen`
        '''

        # Check the constraints are correct
        self.validate_global_constraints()

        parent.add(DirectiveGen(parent, "omp", "begin", "master", ""))

        # Generate the code for all of this node's children
        for child in self.children:
            child.gen_code(parent)

        # Generate the end code for this node
        parent.add(DirectiveGen(parent, "omp", "end", "master", ""))

    def begin_string(self):
        '''Returns the beginning statement of this directive, i.e.
        "omp master". The visitor is responsible for adding the
        correct directive beginning (e.g. "!$").

        :returns: the opening statement of this directive.
        :rtype: str

        '''
        # pylint: disable=no-self-use
        return "omp master"

    def end_string(self):
        '''Returns the end (or closing) statement of this directive, i.e.
        "omp end master". The visitor is responsible for adding the
        correct directive beginning (e.g. "!$").

        :returns: the end statement for this directive.
        :rtype: str

        '''
        # pylint: disable=no-self-use
        return "omp end master"


class OMPParallelDirective(OMPRegionDirective):
    ''' Class representing an OpenMP Parallel directive. '''

    def gen_code(self, parent):
        '''Generate the fortran OMP Parallel Directive and any associated
        code'''
        from psyclone.psyGen import zero_reduction_variables

        private_list = self._get_private_list()

        reprod_red_call_list = self.reductions(reprod=True)
        if reprod_red_call_list:
            # we will use a private thread index variable
            thread_idx = self.scope.symbol_table.\
                lookup_with_tag("omp_thread_index").name
            private_list.append(thread_idx)
            # declare the variable
            parent.add(DeclGen(parent, datatype="integer",
                               entity_decls=[thread_idx]))
        private_str = ",".join(private_list)

        # We're not doing nested parallelism so make sure that this
        # omp parallel region is not already within some parallel region
        self.validate_global_constraints()

        # Check that this OpenMP PARALLEL directive encloses other
        # OpenMP directives. Although it is valid OpenMP if it doesn't,
        # this almost certainly indicates a user error.
        self._encloses_omp_directive()

        calls = self.reductions()

        # first check whether we have more than one reduction with the same
        # name in this Schedule. If so, raise an error as this is not
        # supported for a parallel region.
        names = []
        for call in calls:
            name = call.reduction_arg.name
            if name in names:
                raise GenerationError(
                    "Reduction variables can only be used once in an invoke. "
                    "'{0}' is used multiple times, please use a different "
                    "reduction variable".format(name))
            else:
                names.append(name)

        zero_reduction_variables(calls, parent)

        parent.add(DirectiveGen(parent, "omp", "begin", "parallel",
                                "default(shared), private({0})".
                                format(private_str)))

        if reprod_red_call_list:
            # add in a local thread index
            parent.add(UseGen(parent, name="omp_lib", only=True,
                              funcnames=["omp_get_thread_num"]))
            parent.add(AssignGen(parent, lhs=thread_idx,
                                 rhs="omp_get_thread_num()+1"))

        first_type = type(self.dir_body[0])
        for child in self.dir_body.children:
            if first_type != type(child):
                raise NotImplementedError("Cannot correctly generate code"
                                          " for an OpenMP parallel region"
                                          " containing children of "
                                          "different types")
            child.gen_code(parent)

        parent.add(DirectiveGen(parent, "omp", "end", "parallel", ""))

        if reprod_red_call_list:
            parent.add(CommentGen(parent, ""))
            parent.add(CommentGen(parent, " sum the partial results "
                                  "sequentially"))
            parent.add(CommentGen(parent, ""))
            for call in reprod_red_call_list:
                call.reduction_sum_loop(parent)

    def begin_string(self):
        '''Returns the beginning statement of this directive, i.e.
        "omp parallel". The visitor is responsible for adding the
        correct directive beginning (e.g. "!$").

        :returns: the opening statement of this directive.
        :rtype: str

        '''
        result = "omp parallel default(shared)"
        # TODO #514: not yet working with NEMO, so commented out for now
        # if not self._reprod:
        #     result += self._reduction_string()
        private_list = self._get_private_list()
        private_str = ",".join(private_list)

        if private_str:
            result = "{0}, private({1})".format(result, private_str)
        return result

    def end_string(self):
        '''Returns the end (or closing) statement of this directive, i.e.
        "omp end parallel". The visitor is responsible for adding the
        correct directive beginning (e.g. "!$").

        :returns: the end statement for this directive.
        :rtype: str

        '''
        # pylint: disable=no-self-use
        return "omp end parallel"

    def _get_private_list(self):
        '''
        Returns the variable names used for any loops within a directive
        and any variables that have been declared private by a Kernel
        within the directive.

        :returns: list of variables to declare as thread private.
        :rtype: list of str

        :raises InternalError: if a Kernel has local variable(s) but they \
                               aren't named.
        '''
        from psyclone.psyGen import InvokeSchedule
        result = set()
        # get variable names from all calls that are a child of this node
        for call in self.kernels():
            for variable_name in call.local_vars():
                if variable_name == "":
                    raise InternalError(
                        "call '{0}' has a local variable but its "
                        "name is not set.".format(call.name))
                result.add(variable_name.lower())

        # Now determine scalar variables that must be private:
        var_accesses = VariablesAccessInfo()
        self.reference_accesses(var_accesses)
        for signature in var_accesses.all_signatures:
            accesses = var_accesses[signature].all_accesses
            # Ignore variables that have indices, we only look at scalar
            if accesses[0].is_array():
                continue

            # If a variable is only accessed once, it is either an error
            # or a shared variable - anyway it is not private
            if len(accesses) == 1:
                continue

            # We have at least two accesses. If the first one is a write,
            # assume the variable should be private:
            if accesses[0].access_type == AccessType.WRITE:
                # Check if the write access is inside the parallel loop. If
                # the write is outside of a loop, it is an assignment to
                # a shared variable. Example where jpk is likely used
                # outside of the parallel section later, so it must be
                # declared as shared in order to have its value in other loops:
                # !$omp parallel
                # jpk = 100
                # !omp do
                # do ji = 1, jpk

                # TODO #598: improve the handling of scalar variables.

                # Go up the tree till we either find the InvokeSchedule,
                # which is at the top, or a Loop statement (or no parent,
                # which means we have reached the end of a called kernel).
                parent = accesses[0].node.ancestor((Loop, InvokeSchedule),
                                                   include_self=True)

                if parent and isinstance(parent, Loop):
                    # The assignment to the variable is inside a loop, so
                    # declare it to be private
                    result.add(str(signature).lower())

        # Convert the set into a list and sort it, so that we get
        # reproducible results
        list_result = list(result)
        list_result.sort()
        return list_result

    def validate_global_constraints(self):
        '''
        Perform validation checks that can only be done at code-generation
        time.

        :raises GenerationError: if this OMPDoDirective is not enclosed \
                            within some OpenMP parallel region.
        '''
        if self.ancestor(OMPParallelDirective) is not None:
            raise GenerationError("Cannot nest OpenMP parallel regions.")

    def _encloses_omp_directive(self):
        ''' Check that this Parallel region contains other OpenMP
            directives. While it doesn't have to (in order to be valid
            OpenMP), it is likely that an absence of directives
            is an error on the part of the user. '''
        # We need to recurse down through all our children and check
        # whether any of them are an OMPRegionDirective.
        node_list = self.walk(OMPRegionDirective)
        if not node_list:
            # TODO raise a warning here so that the user can decide
            # whether or not this is OK.
            pass
            # raise GenerationError("OpenMP parallel region does not enclose "
            #                       "any OpenMP directives. This is probably "
            #                       "not what you want.")


class OMPTaskDirective(OMPRegionDirective):
    '''
    Class representing an OpenMP TASK directive in the PSyIR

    :param list children: list of Nodes that are children of this Node.
    :param parent: the Node in the AST that has this directive as a child
    :type parent: :py:class:`psyclone.psyir.nodes.Node`
    '''
    def validate_global_constraints(self):
        '''
        Perform validation checks that can only be done at code-generation
        time.

        :raises GenerationError: if this OMPTaskDirective is not \
                                 enclosed within an OpenMP serial region.
        '''
        # It is only at the point of code generation that we can check for
        # correctness (given that we don't mandate the order that a user
        # can apply transformations to the code). A taskloop
        # directive, we must have an OMPSerialDirective as an
        # ancestor back up the tree.
        if not self.ancestor(OMPSerialDirective):
            raise GenerationError(
                "OMPTaskDirective must be inside an OMP Serial region "
                "but could not find an ancestor node.")

    @staticmethod
    def handle_readonly_reference(ref, firstprivate_list, private_list,
                                  shared_list, in_list, out_list,
                                  parallel_private, start_val, stop_val,
                                  step_val):
        '''
        Process a read-only reference inside the OMP Task Region. Adds the
        Reference str to the appropriate lists for building up clauses.

        FIXME finish docstring
        :param ref: The Reference node to process
        :type ref: TODO
        :param firstprivate_list: The list of firstprivate variables in the \
                                  task region.
        :type firstprivate_list: List of str.
        :param private_list: The list of private variables in the task region.
        :type private_list: List of str.
        :param shared_list: The list of shared variables in the task region.
        :type shared_list: List of str.
        :param in_list: The list of input variables in the task region.
        :type in_list: List of str.
        :param out_list: The list of output variables in the task region.
        :type out_list: List of str.
        :param parallel_private: The list of private variables in the parent \
                                 parallel region.
        :type parallel_private: List of str.
        :param start_val: Start/init value of outermost Loop contained in the \
                          task region.
        :type start_val: ???
        :param stop_val: Stop value of outermost Loop contained in the task \
                         region.
        :type stop_val: ???
        :param step_val: Step value of outermost Loop contained in the task \
                         region.
        :type step_val: ???

        FIXME Raises docstring
        '''
        from psyclone.psyir.backend.fortran import FortranWriter
        writer = FortranWriter()
        if isinstance(ref, (ArrayReference,
                            ArrayOfStructuresReference)):
            # Resolve ArrayReference (AoSReference)
            # Read access array. Find the string representing this
            # array
            name = ref.symbol.name
            index_list = []
            # Check if this is private in the parent parallel
            # region
            is_private = (name in parallel_private)
            # If the reference is private in the parent parallel
            # then it is added to the firstprivate clause for this
            # task if it has not yet been written to (i.e. is not
            # yet in the private clause list).
            if is_private:
                if name not in private_list and name not in \
                        firstprivate_list:
                    firstprivate_list.append(name)
            else:
                # The reference is shared. Since it is an array,
                # we need to check the following restrictions:
                # 1. No ArrayReference or ArrayOfStructuresReference
                # or StructureReference appear in the indexing.
                # 2. Each index is a firstprivate variable, or a 
                # private parent variable that has not yet been
                # declared (in which case we declare it as 
                # firstprivate). Alternatively each index is
                # a BinaryOperation whose children are a
                # Reference to a firstprivate variable and a
                # Literal, with operator of ADD or SUB
                for index in ref.indices:
                    if type(index) is Reference:
                        # Check this is a firstprivate var
                        index_name = index.symbol.name
                        index_private = (index_name in 
                                         parallel_private)
                        if index_private:
                            if index_name in private_list:
                                index_list.append(index_name)
                            elif index_name in firstprivate_list:
                                index_list.append(index_name)
                            else:
                                firstprivate_list.append(index_name)
                                index_list.append(index_name)
                        else:
                            raise GenerationError(
                                    "Shared variable access used "
                                    "as an index inside an "
                                    "OMPTaskDirective which is not "
                                    "supported.")
                    elif type(index) is BinaryOperation:
                        # Binary Operation check
                        OMPTaskDirective.handle_binary_op(index,
                                index_list, firstprivate_list,
                                private_list, parallel_private,
                                start_val, stop_val)
                    else:
                        # Not allowed type appears
                        raise GenerationError(
                                "{0} object is not allowed to "
                                "appear in an Array Index "
                                "expression inside an "
                                "OMPTaskDirective.".format(
                                    type(index).__name__))
            # Add to in_list: name(index1, index2)
            dclause = name + "(" + ", ".join(index_list) + ")"
            in_list.append(dclause)
        elif isinstance(ref, StructureReference):
            # Read access variable. Find the string representing
            # this reference
            name = writer(ref.symbol.name)
            # Check if this is private in the parent parallel 
            # region
            is_private = (name in parallel_private)
            # If the reference is private in the parent parallel,
            # then it is added to the firstprivate clause for this
            # task if it has not yet been written to (i.e. is not
            # yet in the private clause list).
            if is_private:
                if name not in private_list and name not in \
                        firstprivate_list:
                    firstprivate_list.append(name)
            else:
                # Otherwise it was a shared variable. Its not an
                # array so we just add the name to the in_list
                # if not already there. If its already in out_list
                # we still add it as this is the same as an inout
                # dependency
                if name not in in_list:
                    in_list.append(name)
        elif isinstance(ref, Reference):
            # Read access variable. Find the string representing
            # this reference
            name = ref.symbol.name
            # Check if this is private in the parent parallel 
            # region
            is_private = (name in parallel_private)
            # If the reference is private in the parent parallel,
            # then it is added to the firstprivate clause for this
            # task if it has not yet been written to (i.e. is not
            # yet in the private clause list.
            if is_private:
                if name not in private_list and name not in \
                        firstprivate_list:
                    firstprivate_list.append(name)
            else:
                # Otherwise it was a shared variable. Its not an
                # array so we just add the name to the in_list
                # if not already there. If its already in out_list
                # we still add it as this is the same as an inout
                # dependency
                if name not in in_list:
                    in_list.append(name)

    @staticmethod
    def handle_binary_op(node, index_strings, firstprivate_list,
                         private_list, parallel_private,
                         start_val, stop_val):
        '''
        Check a binary operation is safe for using in inside an Array Index
        inside a OMP Task region. Adds the index to the index_strings and
        (first)private_list.

        FIXME finish docstring
        :param node: The BinaryOp node to check 
        :type node: TODO
        :param index_strings: The list of indices in the current array access
        :type index_strings: List of str.
        :param firstprivate_list: The list of firstprivate variables in the \
                                  task region.
        :type firstprivate_list: List of str.
        :param private_list: The list of private variables in the task region.
        :type private_list: List of str.
        :param parallel_private: The list of private variables in the parent \
                                 parallel region.
        :type parallel_private: List of str.
        :param start_val: Start/init value of outermost Loop contained in the \
                          task region.
        :type start_val: ???
        :param stop_val: Stop value of outermost Loop contained in the task \
                         region.
        :type stop_val: ???

        :raises GenerationError: If node.operator is not ADD or SUB
        :raises GenerationError: If the children of node do not contain one \
                                 Reference and one Literal
        :raises GenerationError: If the child Reference is a private variable.
        :raises GenerationError: If the child Reference is a shared variable.
        '''
        from psyclone.psyir.backend.fortran import FortranWriter
        writer = FortranWriter()
        # Binary Operation check
        if node.operator is not \
           BinaryOperation.ADD and \
           node.operator is not \
           BinaryOperation.SUB:
            raise GenerationError(
                "Binary Operator of type {0} used "
                "as in index inside an "
                "OMPTaskDirective which is not "
                "supported".format(
                    node.operator))
        # We have ADD or SUB BinaryOperation
        if not( (type(node.children[0]) is \
           Reference and type(node.children[1]) is\
           Literal) or (type(node.children[0])\
           is Literal and type(node.children[1])\
           is Reference)):
            raise GenerationError(
                "Children of BinaryOperation are of "
                "types {0} and {1}, expected one "
                "Reference and one Literal when"
                " used as an index inside an "
                "OMPTaskDirective.".format(
                    type(node.children[0]).
                    __name__, type(node.children[1]).
                __name__))

        # Have Reference +/- Literal, analyse
        # and create clause appropriately
        index_name = "" 
        if type(node.children[0]) is Reference:
            index_name = writer(node.children[0].symbol)
        if type(node.children[1]) is Reference:
            index_name = writer(node.children[1].symbol)
        index_private = (index_name in 
                         parallel_private)
        if index_private:
            if index_name in private_list:
                # FIXME I think this should be
                # supportable, but need to think
                if node.operator is \
                    BinaryOperation.ADD:
                    index_name = index_name + ("+({0} - {1})"
                           .format(writer(stop_val)
                               ,writer(start_val)))
                else:
                    index_name = index_name + ("-({0} - {1})"
                           .format(writer(stop_val)
                               ,writer(start_val)))
                index_strings.append(index_name)
            elif index_name in firstprivate_list:
                # name +/- stop-start
                if node.operator is \
                    BinaryOperation.ADD:
                    index_name = index_name + ("+({0} - {1})"
                           .format(writer(stop_val)
                               ,writer(start_val)))
                else:
                    index_name = index_name + ("-({0} - {1})"
                           .format(writer(stop_val)
                               ,writer(start_val)))
                index_strings.append(index_name)
            else:
                firstprivate_list.append(index_name)
                # name +/- stop-start 
                if node.operator is \
                    BinaryOperation.ADD:
                    index_name = index_name + ("+({0} - {1})"
                           .format(writer(stop_val)
                               ,writer(start_val)))
                else:
                    index_name = index_name + ("-({0} - {1})"
                           .format(writer(stop_val)
                               ,writer(start_val)))
                index_strings.append(index_name)
        else:
            # FIXME I think this should be
            # supportable, but need to think
            raise GenerationError(
                    "Shared variable access used "
                    "as an index inside an "
                    "OMPTaskDirective which is not "
                    "supported.")

    def compute_clauses(self):
        '''
        TODO
        '''
        from psyclone.psyir.backend.fortran import FortranWriter
        private_list = []
        firstprivate_list = []
        shared_list = []
        in_list = []
        out_list = []

        # Create a FortranWriter to convert nodes to strings
        # TODO: Create issue - support non-Fortran backends
        writer = FortranWriter()

        # TODO Generate extra clauses
        # Find the parent Loop node
        parent_loop = self.ancestor(Loop)

        # Find the parent OMPParallelDirective
        parallel_directive = self.ancestor(OMPParallelDirective)
        parallel_private = parallel_directive._get_private_list()

        node = self.children[0].children[0]

        # Find our loop initialisation, variable and bounds
        loop_var = node.variable
        start_val = node.children[0]
        stop_val = node.children[1]
        step_val = node.children[2]
        schedule = node.children[3]

        # FIXME Disallow transformation if init/stop/step include array references
        # FIXME Handle reduction variables

        # Loop variable is private
        private_list.append(loop_var.name)

        # Any variables used in start_val, stop_val or step_val are firstprivate
        # Get the References used for initialisation
        start_val_refs = start_val.walk(Reference)
        # For all non-array accesses we make them firstprivate

        # TODO Do we worry about array references here? For now we don't allow
        # array references or ArrayOfStruct references
        for ref in start_val_refs:
            if isinstance(ref, (ArrayReference, ArrayOfStructuresReference)):
                raise GenerationError("{0} not yet supported in the start "
                                      "variable of the primary Loop in a "
                                      "OMPTaskDirective node.".format(
                    type(ref).__name__))
            name = writer(ref)
            if ref not in firstprivate_list:
                firstprivate_list.append(name)

        stop_val_refs = stop_val.walk(Reference)
        for sig in stop_val_refs:
            if isinstance(ref, (ArrayReference, ArrayOfStructuresReference)):
                raise GenerationError("{0} not yet supported in the stop "
                                      "variable of the primary Loop in a "
                                      "OMPTaskDirective node.".format(
                    type(ref).__name__))
            name = writer(ref)
            if ref not in firstprivate_list:
                firstprivate_list.append(name)

        
        step_val_refs = step_val.walk(Reference)
        for sig in step_val_refs:
            if isinstance(ref, (ArrayReference, ArrayOfStructuresReference)):
                raise GenerationError("{0} not yet supported in the step "
                                      "variable of the primary Loop in a "
                                      "OMPTaskDirective node.".format(
                    type(ref).__name__))
            name = writer(ref)
            if ref not in firstprivate_list:
                firstprivate_list.append(name)

        # Look through the schedule and work out data sharing clauses.
        statements = schedule.walk((Assignment, IfBlock, Loop))
        for statement in statements:
            if isinstance(statement, Assignment):
                lhs = statement.children[0]
                rhs = statement.children[1]
                # check if lhs is array access
                if isinstance(lhs, ArrayReference):
                    # Resolve ArrayReference
                    # We write to this reference, so it is shared and depend
                    # out on array(variable) and other depending on + or -
                    # in the indexing
                    sig, indices = lhs.get_signature_and_indices()
                    name = str(sig)
                    # Check if this is private in the parent parallel
                    # region
                    is_private = (name in parallel_private)
                    if is_private:
                        #FIXME Think about what happens if this is declared private
                        assert False
                    index_strings = []
                    loop_reference = False
                    # Do something with indices
                    for index in indices[0]:
                        if isinstance(index, Literal):
                            # Literals are just value
                            value = writer(index)
                            index_strings.append(value)
                        elif isinstance(index, Reference):
                            # Refrences also just treated as values
                            index_strings.append(writer(index))
                            if index.symbol == loop_var:
                                loop_reference = True
                        elif isinstance(index, BinaryOperation):
                            OMPTaskDirective.handle_binary_op(index,
                                    index_strings, firstprivate_list,
                                    private_list, parallel_private,
                                    start_val, stop_val)
                        else:
                            # Not allowed type appears
                            raise GenerationError(
                                    "{0} object is not allowed to "
                                    "appear in an Array Index "
                                    "expression inside an "
                                    "OMPTaskDirective.".format(
                                        type(index).__name__))
                    # So we have a list of indices [index1, index2, index3] so convert these
                    # to a depend clause
                    depend_clause = name + "(" + ", ".join(index_strings) + ")"
                    if name not in shared_list:
                        shared_list.append(name)
                    if depend_clause not in out_list:
                        out_list.append(depend_clause)
                elif isinstance(lhs, ArrayOfStructuresReference):
                    # ArrayOfStructuresReference
                    # We write to this reference, so it is shared and depend out on
                    # array(variable) and other depending on +  or - in the indexing
                    sig, indices = lhs.get_signature_and_indices()
                    name = writer(sig.symbol.name)
                    # Check if this is private in the parent parallel
                    # region
                    is_private = (name in parallel_private)
                    if is_private:
                        #FIXME Think about what happens if this is declared private
                        assert False
                    index_strings = []
                    loop_reference = False
                    # Do something with indices
                    for index in indices:
                        if isinstance(index, Literal):
                            # Literals are just value
                            value = writer(index)
                            index_strings.append(value)
                        elif isinstance(index, Reference):
                            # Refrences also just treated as values
                            index_strings.append(writer(index))
                            if index.symbol == loop_var.symbol:
                                loop_reference = True
                        elif isinstance(index, BinaryOperation):
                            # Binary Operation check
                            OMPTaskDirective.handle_binary_op(index,
                                    index_strings, firstprivate_list,
                                    private_list, parallel_private,
                                    start_val, stop_val)
                        else:
                            # Not allowed type appears
                            raise GenerationError(
                                    "{0} object is not allowed to "
                                    "appear in an Array Index "
                                    "expression inside an "
                                    "OMPTaskDirective.".format(
                                        type(index).__name__))
                    # So we have a list of indices [index1, index2, index3] so convert these
                    # to a depend clause
                    depend_clause = name + "(" + index_strings.join(", ") + ")"
                    if name not in shared_list:
                        shared_list.append(name)
                    if depend_clause not in out_list:
                       out_list.append(depend_clause)
                elif isinstance(lhs, StructureReference):
                    # Resolve StructureReference
                    # We only need the Structure name, this is probably wrong
                    name = writer(lhs.symbol.name)
                    is_private = (name in parallel_private)
                    if not is_private:
                        if name not in shared_list:
                            shared_list.append(name)
                        if name not in out_list:
                            out_list.append(name)
                elif isinstance(lhs, Reference):
                    #Resolve reference
                    name = writer(lhs)
                    is_private = (name in parallel_private)
                    if not is_private:
                        if name not in shared_list:
                            shared_list.append(name)
                        if name not in out_list:
                            out_list.append(name)

                # Handle rhs References
                references = rhs.walk(Reference)
                for ref in references:
                    OMPTaskDirective.handle_readonly_reference(ref,
                            firstprivate_list, private_list, shared_list,
                            in_list, out_list, parallel_private, start_val,
                            stop_val, step_val)
            elif isinstance(statement, IfBlock):
                # Resolve IfBlock
                # We only need to look at the If condition (DataNode, child[0])
                # The other statements will be covered by Assignment or Loop
                condition = statement.children[0]
                # Find all the References
                references = condition.walk(Reference)
                for ref in references:
                    OMPTaskDirective.handle_readonly_reference(ref,
                            firstprivate_list, private_list, shared_list,
                            in_list, out_list, parallel_private, start_val,
                            stop_val, step_val)
            elif isinstance(statement, Loop):
                # Resolve Loop
                # FIXME Handle Loop variable
                var = statement.variable
                private_list.append(var.name)
                start = statement.children[0]
                stop = statement.children[1]
                end = statement.children[2]
                # Don't need to worry about schedule, anything inside that will
                # be caught by the outer walk.
                for ref in start.walk(Reference):
                    OMPTaskDirective.handle_readonly_reference(ref,
                            firstprivate_list, private_list, shared_list,
                            in_list, out_list, parallel_private, start_val,
                            stop_val, step_val)
                for ref in stop.walk(Reference):
                    OMPTaskDirective.handle_readonly_reference(ref,
                            firstprivate_list, private_list, shared_list,
                            in_list, out_list, parallel_private, start_val,
                            stop_val, step_val)
                for ref in end.walk(Reference):
                    OMPTaskDirective.handle_readonly_reference(ref,
                            firstprivate_list, private_list, shared_list,
                            in_list, out_list, parallel_private, start_val,
                            stop_val, step_val)

        return (private_list, firstprivate_list, shared_list,
                in_list, out_list)

    def gen_code(self, parent):
        '''
        Generate the f2pygen AST entries in the Schedule for this OpenMP
        taskloop directive.

        :param parent: the parent Node in the Schedule to which to add our \
                       content.
        :type parent: sub-class of :py:class:`psyclone.f2pygen.BaseGen`

        '''
        self.validate_global_constraints()
        clause_list = []
        private_list, firstprivate_list, shared_list, in_list, out_list = \
                self.compute_clauses()

        # Build up the extra clauses.
        if len(private_list) != 0:
            clause_list.append("private({0})".format(", ".join(private_list)))
        if len(shared_list) != 0:
            clause_list.append("shared({0})".format(", ".join(shared_list)))
        if len(firstprivate_list) != 0:
            clause_list.append("firstprivate({0})".format(", ".join(firstprivate_list)))
        if len(in_list) != 0:
            clause_list.append("depend(in: {0} )".format(", ".join(in_list)))
        if len(out_list) != 0:
            clause_list.append("depend(out: {0} )".format(", ".join(out_list)))


        # Generate the string containing the required clauses
        extra_clauses = ", ".join(clause_list)
        parent.add(DirectiveGen(parent, "omp", "begin", "task",
                                extra_clauses))

        for child in self.children:
            child.gen_code(parent)

        # make sure the directive occurs straight after the loop body
        position = parent.previous_loop()
        parent.add(DirectiveGen(parent, "omp", "end", "task", ""),
                   position=["after", position])

    def begin_string(self):
        '''Returns the beginning statement of this directive, i.e.
        "omp task ...". The visitor is responsible for adding the
        correct directive beginning (e.g. "!$").

        :returns: the beginning statement for this directive.
        :rtype: str

        '''
        clause_list = []
        private_list, firstprivate_list, shared_list, in_list, out_list = \
                self.compute_clauses()

        # Build up the extra clauses.
        if len(private_list) != 0:
            clause_list.append("private({0})".format(", ".join(private_list)))
        if len(shared_list) != 0:
            clause_list.append("shared({0})".format(", ".join(shared_list)))
        if len(firstprivate_list) != 0:
            clause_list.append("firstprivate({0})".format(", ".join(firstprivate_list)))
        if len(in_list) != 0:
            clause_list.append("depend(in: {0} )".format(", ".join(in_list)))
        if len(out_list) != 0:
            clause_list.append("depend(out: {0} )".format(", ".join(out_list)))


        # Generate the string containing the required clauses
        extra_clauses = ", ".join(clause_list)
        return "omp task {0}".format(extra_clauses)

    def end_string(self):
        '''Returns the end (or closing) statement of this directive, i.e.
        "omp end task". The visitor is responsible for adding the
        correct directive beginning (e.g. "!$").

        :returns: the end statement for this directive.
        :rtype: str

        '''
        # pylint: disable=no-self-use
        return "omp end task"

class OMPTaskloopDirective(OMPRegionDirective):
    '''
    Class representing an OpenMP TASKLOOP directive in the PSyIR.

    :param list children: list of Nodes that are children of this Node.
    :param parent: the Node in the AST that has this directive as a child.
    :type parent: :py:class:`psyclone.psyir.nodes.Node`
    :param grainsize: The grainsize value used to specify the grainsize \
                      clause on this OpenMP directive. If this is None \
                      the grainsize clause is not applied. Default \
                      value is None.
    :type grainsize: int or None.
    :param num_tasks: The num_tasks value used to specify the num_tasks \
                      clause on this OpenMP directive. If this is None \
                      the num_tasks clause is not applied. Default value \
                      is None.
    :type num_tasks: int or None.
    :param nogroup: Whether the nogroup clause should be used for this node. \
                    Default value is False
    :type nogroup: bool

    :raises GenerationError: if this OMPTaskloopDirective has both \
                             a grainsize and num_tasks value \
                             specified.
    '''
    # This specification respects the mutual exclusion of OMPGransizeClause
    # and OMPNumTasksClause, but adds an additional ordering requirement.
    # Other specifications to soften the ordering requirement are possible,
    # but need additional checks in the global constraints instead.
    _children_valid_format = ("Schedule, [OMPGrainsizeClause | "
                              "OMPNumTasksClause], [OMPNogroupClause]")

    # pylint: disable=too-many-arguments
    def __init__(self, children=None, parent=None, grainsize=None,
                 num_tasks=None, nogroup=False):
        # These remain primarily for the gen_code interface
        self._grainsize = grainsize
        self._num_tasks = num_tasks
        self._nogroup = nogroup
        if self._grainsize is not None and self._num_tasks is not None:
            raise GenerationError(
                "OMPTaskloopDirective must not have both grainsize and "
                "numtasks clauses specified.")
        super(OMPTaskloopDirective, self).__init__(children=children,
                                                   parent=parent)
        if self._grainsize is not None:
            child = [Literal(f"{grainsize}", INTEGER_TYPE)]
            self._children.append(OMPGrainsizeClause(children=child))
        if self._num_tasks is not None:
            child = [Literal(f"{num_tasks}", INTEGER_TYPE)]
            self._children.append(OMPNumTasksClause(children=child))
        if self._nogroup:
            self._children.append(OMPNogroupClause())

    @staticmethod
    def _validate_child(position, child):
        '''
         Decides whether a given child and position are valid for this node.
         The rules are:
         1. Child 0 must always be a Schedule.
         2. Child 1 may be either a OMPGrainsizeClause or OMPNumTasksClause, \
            or if neither of those clauses are present, it may be a \
            OMPNogroupClause.
         3. Child 2 must always be a OMPNogroupClause, and can only exist if \
            child 1 is a OMPGrainsizeClause or OMPNumTasksClause.

        :param int position: the position to be validated.
        :param child: a child to be validated.
        :type child: :py:class:`psyclone.psyir.nodes.Node`

        :return: whether the given child and position are valid for this node.
        :rtype: bool

        '''
        if position == 0:
            return isinstance(child, Schedule)
        if position == 1:
            return isinstance(child, (OMPGrainsizeClause, OMPNumTasksClause,
                                      OMPNogroupClause))
        if position == 2:
            return isinstance(child, OMPNogroupClause)
        return False

    @property
    def nogroup(self):
        '''
        :returns: the nogroup clause status of this node.
        :rtype: bool
        '''
        return self._nogroup

    def validate_global_constraints(self):
        '''
        Perform validation checks that can only be done at code-generation
        time.

        :raises GenerationError: if this OMPTaskloopDirective is not \
                                 enclosed within an OpenMP serial region.
        :raises GenerationError: if this OMPTaskloopDirective has two
                                 Nogroup clauses as children.
        '''
        # It is only at the point of code generation that we can check for
        # correctness (given that we don't mandate the order that a user
        # can apply transformations to the code). A taskloop
        # directive, we must have an OMPSerialDirective as an
        # ancestor back up the tree.
        if not self.ancestor(OMPSerialDirective):
            raise GenerationError(
                "OMPTaskloopDirective must be inside an OMP Serial region "
                "but could not find an ancestor node")

        # Check children are well formed.
        # _validate_child will ensure position 0 and 1 are valid.
        if len(self._children) == 3 and isinstance(self._children[1],
                                                   OMPNogroupClause):
            raise GenerationError(
                "OMPTaskloopDirective has two Nogroup clauses as children "
                "which is not allowed.")

        super(OMPTaskloopDirective, self).validate_global_constraints()

    def gen_code(self, parent):
        '''
        Generate the f2pygen AST entries in the Schedule for this OpenMP
        taskloop directive.

        :param parent: the parent Node in the Schedule to which to add our \
                       content.
        :type parent: sub-class of :py:class:`psyclone.f2pygen.BaseGen`
        :raises GenerationError: if this "!$omp taskloop" is not enclosed \
                                 within an OMP Parallel region and an OMP \
                                 Serial region.

        '''
        self.validate_global_constraints()

        extra_clauses = ""
        # Find the specified clauses
        clause_list = []
        if self._grainsize is not None:
            clause_list.append("grainsize({0})".format(self._grainsize))
        if self._num_tasks is not None:
            clause_list.append("num_tasks({0})".format(self._num_tasks))
        if self._nogroup:
            clause_list.append("nogroup")
        # Generate the string containing the required clauses
        extra_clauses = ", ".join(clause_list)

        parent.add(DirectiveGen(parent, "omp", "begin", "taskloop",
                                extra_clauses))

        self.dir_body.gen_code(parent)

        # make sure the directive occurs straight after the loop body
        position = parent.previous_loop()
        parent.add(DirectiveGen(parent, "omp", "end", "taskloop", ""),
                   position=["after", position])

    def begin_string(self):
        '''Returns the beginning statement of this directive, i.e.
        "omp taskloop ...". The visitor is responsible for adding the
        correct directive beginning (e.g. "!$").

        :returns: the beginning statement for this directive.
        :rtype: str

        '''
        # pylint: disable=no-self-use
        return "omp taskloop"

    def end_string(self):
        '''Returns the end (or closing) statement of this directive, i.e.
        "omp end taskloop". The visitor is responsible for adding the
        correct directive beginning (e.g. "!$").

        :returns: the end statement for this directive.
        :rtype: str

        '''
        # pylint: disable=no-self-use
        return "omp end taskloop"


class OMPDoDirective(OMPRegionDirective):
    '''
    Class representing an OpenMP DO directive in the PSyIR.

    :param list children: list of Nodes that are children of this Node.
    :param parent: the Node in the AST that has this directive as a child.
    :type parent: :py:class:`psyclone.psyir.nodes.Node`
    :param str omp_schedule: the OpenMP schedule to use.
    :param bool reprod: whether or not to generate code for run-reproducible \
                        OpenMP reductions.

    '''
    def __init__(self, children=None, parent=None, omp_schedule="static",
                 reprod=None):

        if reprod is None:
            self._reprod = Config.get().reproducible_reductions
        else:
            self._reprod = reprod

        self._omp_schedule = omp_schedule

        # Call the init method of the base class once we've stored
        # the OpenMP schedule
        super(OMPDoDirective, self).__init__(children=children,
                                             parent=parent)

    def __eq__(self, other):
        '''
        Checks whether two nodes are equal. Two OMPDoDirective nodes are equal
        if they have the same schedule, the same reproducible reduction option
        (and the inherited equality is True).

        :param object other: the object to check equality to.

        :returns: whether other is equal to self.
        :rtype: bool
        '''
        is_eq = super().__eq__(other)
        is_eq = is_eq and self.omp_schedule == other.omp_schedule
        is_eq = is_eq and self.reprod == other.reprod

        return is_eq

    def node_str(self, colour=True):
        '''
        Returns the name of this node with (optional) control codes
        to generate coloured output in a terminal that supports it.

        :param bool colour: whether or not to include colour control codes.

        :returns: description of this node, possibly coloured.
        :rtype: str
        '''
        if self.reductions():
            reprod = "reprod={0}".format(self._reprod)
        else:
            reprod = ""
        return "{0}[{1}]".format(self.coloured_name(colour), reprod)

    def _reduction_string(self):
        ''' Return the OMP reduction information as a string '''
        reduction_str = ""
        for reduction_type in AccessType.get_valid_reduction_modes():
            reductions = self._get_reductions_list(reduction_type)
            for reduction in reductions:
                reduction_str += ", reduction({0}:{1})".format(
                    OMP_OPERATOR_MAPPING[reduction_type], reduction)
        return reduction_str

    @property
    def omp_schedule(self):
        '''
        :returns: the omp_schedule for this object.
        :rtype: str
        '''
        return self._omp_schedule

    @property
    def reprod(self):
        ''' returns whether reprod has been set for this object or not '''
        return self._reprod

    def validate_global_constraints(self):
        '''
        Perform validation checks that can only be done at code-generation
        time.

        :raises GenerationError: if this OMPDoDirective is not enclosed \
                            within some OpenMP parallel region.
        '''
        # It is only at the point of code generation that we can check for
        # correctness (given that we don't mandate the order that a user
        # can apply transformations to the code). As a loop
        # directive, we must have an OMPParallelDirective as an ancestor
        # somewhere back up the tree.
        if not self.ancestor(OMPParallelDirective,
                             excluding=OMPParallelDoDirective):
            raise GenerationError(
                "OMPDoDirective must be inside an OMP parallel region but "
                "could not find an ancestor OMPParallelDirective node")

        self._validate_single_loop()

        super(OMPDoDirective, self).validate_global_constraints()

    def _validate_single_loop(self):
        '''
        Checks that this directive is only applied to a single Loop node.

        :raises GenerationError: if this directive has more than one child.
        :raises GenerationError: if the child of this directive is not a Loop.

        '''
        if len(self.dir_body.children) != 1:
            raise GenerationError(
                "An {0} can only be applied to a single loop "
                "but this Node has {1} children: {2}".
                format(type(self).__name__, len(self.dir_body.children),
                       self.dir_body.children))

        if not isinstance(self.dir_body[0], Loop):
            raise GenerationError(
                "An {0} can only be applied to a loop "
                "but this Node has a child of type '{1}'".format(
                    type(self).__name__, type(self.dir_body[0]).__name__))

    def gen_code(self, parent):
        '''
        Generate the f2pygen AST entries in the Schedule for this OpenMP do
        directive.

        :param parent: the parent Node in the Schedule to which to add our \
                       content.
        :type parent: sub-class of :py:class:`psyclone.f2pygen.BaseGen`
        :raises GenerationError: if this "!$omp do" is not enclosed within \
                                 an OMP Parallel region.

        '''
        self.validate_global_constraints()

        if self._reprod:
            local_reduction_string = ""
        else:
            local_reduction_string = self._reduction_string()

        # As we're a loop we don't specify the scope
        # of any variables so we don't have to generate the
        # list of private variables
        options = "schedule({0})".format(self._omp_schedule) + \
                  local_reduction_string
        parent.add(DirectiveGen(parent, "omp", "begin", "do", options))

        for child in self.children:
            child.gen_code(parent)

        # make sure the directive occurs straight after the loop body
        position = parent.previous_loop()
        parent.add(DirectiveGen(parent, "omp", "end", "do", ""),
                   position=["after", position])

    def begin_string(self):
        '''Returns the beginning statement of this directive, i.e.
        "omp do ...". The visitor is responsible for adding the
        correct directive beginning (e.g. "!$").

        :returns: the beginning statement for this directive.
        :rtype: str

        '''
        return "omp do schedule({0})".format(self._omp_schedule)

    def end_string(self):
        '''Returns the end (or closing) statement of this directive, i.e.
        "omp end do". The visitor is responsible for adding the
        correct directive beginning (e.g. "!$").

        :returns: the end statement for this directive.
        :rtype: str

        '''
        # pylint: disable=no-self-use
        return "omp end do"


class OMPParallelDoDirective(OMPParallelDirective, OMPDoDirective):
    ''' Class for the !$OMP PARALLEL DO directive. This inherits from
        both OMPParallelDirective (because it creates a new OpenMP
        thread-parallel region) and OMPDoDirective (because it
        causes a loop to be parallelised). '''

    def __init__(self, children=[], parent=None, omp_schedule="static"):
        OMPDoDirective.__init__(self,
                                children=children,
                                parent=parent,
                                omp_schedule=omp_schedule)

    def gen_code(self, parent):

        # We're not doing nested parallelism so make sure that this
        # omp parallel do is not already within some parallel region
        from psyclone.psyGen import zero_reduction_variables
        self.validate_global_constraints()

        calls = self.reductions()
        zero_reduction_variables(calls, parent)
        private_str = ",".join(self._get_private_list())
        parent.add(DirectiveGen(parent, "omp", "begin", "parallel do",
                                "default(shared), private({0}), "
                                "schedule({1})".
                                format(private_str, self._omp_schedule) +
                                self._reduction_string()))
        for child in self.children:
            child.gen_code(parent)

        # make sure the directive occurs straight after the loop body
        position = parent.previous_loop()
        parent.add(DirectiveGen(parent, *self.end_string().split()),
                   position=["after", position])

    def begin_string(self):
        '''Returns the beginning statement of this directive, i.e.
        "omp do ...". The visitor is responsible for adding the
        correct directive beginning (e.g. "!$").

        :returns: the beginning statement for this directive.
        :rtype: str

        '''
        private_str = ",".join(self._get_private_list())
        return ("omp parallel do default(shared), private({0}), "
                "schedule({1})".format(private_str, self._omp_schedule) +
                self._reduction_string())

    def end_string(self):
        '''
        :returns: the closing statement for this directive.
        :rtype: str
        '''
        # pylint: disable=no-self-use
        return "omp end parallel do"

    def validate_global_constraints(self):
        '''
        Perform validation checks that can only be done at code-generation
        time.

        '''
        super(OMPParallelDoDirective, self).validate_global_constraints()

        self._validate_single_loop()


class OMPTargetDirective(OMPRegionDirective):
    ''' Class for the !$OMP TARGET directive that offloads the code contained
    in its region into an accelerator device. '''

    def begin_string(self):
        '''Returns the beginning statement of this directive, i.e.
        "omp target". The visitor is responsible for adding the
        correct directive beginning (e.g. "!$").

        :returns: the opening statement of this directive.
        :rtype: str

        '''
        # pylint: disable=no-self-use
        return "omp target"

    def end_string(self):
        '''Returns the end (or closing) statement of this directive, i.e.
        "omp end target". The visitor is responsible for adding the
        correct directive beginning (e.g. "!$").

        :returns: the end statement for this directive.
        :rtype: str

        '''
        # pylint: disable=no-self-use
        return "omp end target"


class OMPLoopDirective(OMPRegionDirective):
    ''' Class for the !$OMP LOOP directive that specifies that the iterations
    of the associated loops may execute concurrently.

    :param int collapse: optional number of nested loops to collapse into a \
        single iteration space to parallelise. Defaults to None.
    '''

    def __init__(self, collapse=None, **kwargs):
        super(OMPLoopDirective, self).__init__(**kwargs)
        self._collapse = None
        self.collapse = collapse  # Use setter with error checking

    def __eq__(self, other):
        '''
        Checks whether two nodes are equal. Two OMPLoopDirective nodes are
        equal if they have the same collapse status and the inherited
        equality is true.

        :param object other: the object to check equality to.

        :returns: whether other is equal to self.
        :rtype: bool
        '''
        is_eq = super().__eq__(other)
        is_eq = is_eq and self.collapse == other.collapse

        return is_eq

    @property
    def collapse(self):
        '''
        :returns: the value of the collapse clause.
        :rtype: int or NoneType
        '''
        return self._collapse

    @collapse.setter
    def collapse(self, value):
        '''
        :param value: optional number of nested loop to collapse into a \
            single iteration space to parallelise. Defaults to None.
        :type value: int or NoneType.

        :raises TypeError: if the collapse value given is not an integer \
            or NoneType.
        :raises ValueError: if the collapse integer given is not positive.

        '''
        if value is not None and not isinstance(value, int):
            raise TypeError(
                "The OMPLoopDirective collapse clause must be a positive "
                "integer or None, but value '{0}' has been given."
                "".format(value))

        if value is not None and value <= 0:
            raise ValueError(
                "The OMPLoopDirective collapse clause must be a positive "
                "integer or None, but value '{0}' has been given."
                "".format(value))

        self._collapse = value

    def node_str(self, colour=True):
        ''' Returns the name of this node with (optional) control codes
        to generate coloured output in a terminal that supports it.

        :param bool colour: whether or not to include colour control codes.

        :returns: description of this node, possibly coloured.
        :rtype: str
        '''
        text = self.coloured_name(colour)
        if self._collapse:
            text += "[collapse={0}]".format(str(self._collapse))
        else:
            text += "[]"
        return text

    def begin_string(self):
        ''' Returns the beginning statement of this directive, i.e. "omp loop".
        The visitor is responsible for adding the correct directive beginning
        (e.g. "!$").

        :returns: the opening statement of this directive.
        :rtype: str

        '''
        string = "omp loop"
        if self._collapse:
            string += " collapse({0})".format(str(self._collapse))
        return string

    def end_string(self):
        '''Returns the end (or closing) statement of this directive, i.e.
        "omp end loop". The visitor is responsible for adding the
        correct directive beginning (e.g. "!$").

        :returns: the end statement for this directive.
        :rtype: str

        '''
        # pylint: disable=no-self-use
        return "omp end loop"

    def validate_global_constraints(self):
        ''' Perform validation of those global constraints that can only be
        done at code-generation time.

        :raises GenerationError: if this OMPLoopDirective has more than one \
            child in its associated schedule.
        :raises GenerationError: if the schedule associated with this \
            OMPLoopDirective does not contain a Loop.
        :raises GenerationError: this directive must be inside a omp target \
            or parallel region.
        :raises GenerationError: if this OMPLoopDirective has a collapse \
            clause but it doesn't have the expected number of nested Loops.

        '''
        if len(self.dir_body.children) != 1:
            raise GenerationError(
                "OMPLoopDirective must have exactly one child in its "
                "associated schedule but found {0}.".format(
                    self.dir_body.children))

        if not isinstance(self.dir_body.children[0], Loop):
            raise GenerationError(
                "OMPLoopDirective must have a Loop as child of its associated "
                "schedule but found '{0}'.".format(self.dir_body.children[0]))

        if not self.ancestor((OMPTargetDirective, OMPParallelDirective)):
            # Also omp teams or omp threads regions but these are not supported
            # in the PSyIR
            raise GenerationError(
                f"OMPLoopDirective must be inside a OMPTargetDirective or a "
                f"OMPParallelDirective, but '{self}' is not.")

        # If there is a collapse clause, there must be as many immediately
        # nested loops as the collapse value
        if self._collapse:
            cursor = self.dir_body.children[0]
            for depth in range(self._collapse):
                if not isinstance(cursor, Loop):
                    raise GenerationError(
                        "OMPLoopDirective must have as many immediately nested"
                        " loops as the collapse clause specifies but '{0}' "
                        "has a collpase={1} and the nested statement at depth "
                        "{2} is a {3} rather than a Loop."
                        "".format(self, self._collapse, depth,
                                  type(cursor).__name__))
                cursor = cursor.loop_body.children[0]

        super(OMPLoopDirective, self).validate_global_constraints()


# For automatic API documentation generation
__all__ = ["OMPRegionDirective", "OMPParallelDirective", "OMPSingleDirective",
           "OMPMasterDirective", "OMPDoDirective", "OMPParallelDoDirective",
           "OMPSerialDirective", "OMPTaskloopDirective", "OMPTargetDirective",
           "OMPTaskwaitDirective", "OMPDirective", "OMPStandaloneDirective",
           "OMPLoopDirective", "OMPDeclareTargetDirective"]
