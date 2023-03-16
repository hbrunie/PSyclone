# -----------------------------------------------------------------------------
# BSD 3-Clause License
#
# Copyright (c) 2023, Science and Technology Facilities Council.
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
# Author: R. W. Ford, STFC Daresbury Lab

'''This module implements a class that encapsulates rules that map
   LFRic kernel metadata to kernel arguments.

'''
from psyclone.domain.lfric import LFRicConstants
from psyclone.domain.lfric.kernel import (
    OperatorArgMetadata, ColumnwiseOperatorArgMetadata, FieldArgMetadata,
    FieldVectorArgMetadata, InterGridArgMetadata, InterGridVectorArgMetadata,
    ScalarArgMetadata)
from psyclone.errors import InternalError

# pylint: disable=too-many-branches
# pylint: disable=too-many-statements
# pylint: disable=too-few-public-methods


class MetadataToArgumentsRules():
    '''This class encapsulates rules to map LFRic kernel metadata to
    kernel arguments. It does this by calling class methods each of
    which which represent a particular kernel argument or set of
    arguments. It calls these in the order that the arguments should
    be found in the kernel metadata. The particular methods called and
    order that these methods are called are determined by the supplied
    kernel metadata.

    Kernel argument information from kernel metadata can be used for
    more than one thing, e.g. to create or check arguments within a
    kernel and their declarations (using PSyIR) or to create the
    arguments in the calling method from the generated PSy-layer code,
    which at some point will (mostly) need to be dereferenced from
    existing datatypes, such as fields, or to create appropriate
    algorithm PSyIR for a) the calling routine or b) the subroutine
    body in the PSy-layer. Subclasses of this class can be implemented
    for these different requirements.

    '''
    _metadata = None
    _info = None

    @classmethod
    def mapping(cls, metadata, info=None):
        '''Takes kernel metadata as input and returns whatever is added to the
        _info variable. This class adds nothing to the _info variable,
        it is up to the subclass to do this. The variable is treated
        as a container. The optional info argument allows the subclass
        to add to an existing object if required.

        :param metadata: the kernel metadata.
        :type metadata: \
            py:class:`psyclone.domain.lfric.kernel.LFRicKernelMetadata`
        :param info: optional object to initialise the _info \
            variable. Defaults to None.
        :type info: :py:class:`Object`

        '''
        cls._initialise(info)
        cls._metadata = metadata
        cls._generate(metadata)
        return cls._info

    @classmethod
    def _initialise(cls, info):
        '''Initialise the _info variable. This is implemented as its own
        method to allow for simple subclassing (i.e. the mapping
        method should not need to be subclassed.

        :param info: object to initialise the _info variable.
        :type info: :py:class:`Object`

        '''
        cls._info = info

    @classmethod
    def _cell_position(cls):
        '''A cell position argument.'''

    @classmethod
    def _mesh_height(cls):
        '''A mesh height argument.'''

    @classmethod
    def _mesh_ncell2d_no_halos(cls):
        '''Argument providing the number of columns in the mesh ignoring
        halos.

        '''

    @classmethod
    def _mesh_ncell2d(cls):
        '''Argument providing the number of columns in the mesh including
        halos.

        '''

    @classmethod
    def _cell_map(cls):
        '''Arguments providing a mapping from coarse to fine mesh for the
        current column.

        '''

    @classmethod
    def _scalar(cls, meta_arg):
        '''Argument providing an LFRic scalar value.

        :param meta_arg: the metadata associated with this scalar argument.
        :type meta_arg: \
            :py:class:`psyclone.domain.lfric.kernel.ScalarArgMetadata`

        '''

    @classmethod
    def _field(cls, meta_arg):
        '''Argument providing an LFRic field.

        :param meta_arg: the metadata associated with this field argument.
        :type meta_arg: \
            :py:class:`psyclone.domain.lfric.kernel.FieldArgMetadata`

        '''

    @classmethod
    def _field_vector(cls, meta_arg):
        '''Arguments providing an LFRic field vector.

        :param meta_arg: the metadata associated with this field \
            vector argument.
        :type meta_arg: \
            :py:class:`psyclone.domain.lfric.kernel.FieldVectorArgMetadata`

        '''

    @classmethod
    def _operator(cls, meta_arg):
        '''Arguments providing an LMA operator.

        :param meta_arg: the metadata associated with the operator \
            arguments.
        :type meta_arg: \
            :py:class:`psyclone.domain.lfric.kernel.OperatorArgMetadata`

        '''

    @classmethod
    def _cma_operator(cls, meta_arg):
        '''Arguments providing a columnwise operator.

        :param meta_arg: the metadata associated with the CMA operator \
            arguments.
        :type meta_arg: :py:class:`psyclone.domain.lfric.kernel.\
            ColumnwiseOperatorArgMetadata`

        '''

    @classmethod
    def _ref_element_properties(cls, meta_ref_element):
        '''Arguments required if there are reference element properties
        specified in the metadata.

        '''

    @classmethod
    def _mesh_properties(cls, meta_mesh):
        '''All arguments required for mesh properties specified in the kernel
        metadata.

        :param meta_mesh: the metadata capturing the mesh properties \
            required by the kernel.
        :type meta_mesh: List[\
            :py:class:`psyclone.domain.lfric.kernel.MetaMeshArgMetadata`]

        '''

    @classmethod
    def _fs_common(cls, function_space):
        '''Arguments associated with a function space that are common to
        fields and operators.

        :param str function_space: the current function space.

        '''

    @classmethod
    def _fs_compulsory_field(cls, function_space):
        '''Compulsory arguments for this function space.

        :param str function_space: the current function space.

        '''

    @classmethod
    def _fs_intergrid(cls, meta_arg):
        '''Function-space related arguments for an intergrid kernel.

        :param meta_arg: the metadata capturing the InterGrid argument \
            required by the kernel.
        :type meta_arg: \
        :py:class:`psyclone.domain.lfric.kernel.InterGridArgMetadata`]

        '''

    @classmethod
    def _basis(cls, function_space):
        '''Arguments associated with basis functions on the supplied function
        space.

        :param str function_space: the current function space.

        '''

    @classmethod
    def _diff_basis(cls, function_space):
        '''Arguments associated with differential basis functions on the
        supplied function space.

        :param str function_space: the current function space.

        '''

    @classmethod
    def _quad_rule(cls, shapes):
        '''Quadrature information is required (gh_shape =
        gh_quadrature_*). Shape information is provided for each shape
        in the order specified in the gh_shape metadata.

        :param shapes: the metadata capturing the quadrature shapes \
            required by the kernel.
        :type shapes: List[str]

        '''

    @classmethod
    def _field_bcs_kernel(cls):
        '''Fix for the field boundary condition kernel.'''

    @classmethod
    def _operator_bcs_kernel(cls):
        '''Fix for the operator boundary condition kernel.'''

    @classmethod
    def _stencil_2d_unknown_extent(cls, meta_arg):
        '''The field entry has a stencil access of type cross2d.

        :param meta_arg: the metadata associated with a field argument \
            with a cross2d stencil access.
        :type meta_arg: \
            :py:class:`psyclone.domain.lfric.kernel.FieldArgMetadata`

        '''

    @classmethod
    def _stencil_2d_max_extent(cls, meta_arg):
        '''The field entry has a stencil access of type cross2d.

        :param meta_arg: the metadata associated with a field argument \
            with a cross2d stencil access.
        :type meta_arg: \
            :py:class:`psyclone.domain.lfric.kernel.FieldArgMetadata`

        '''

    @classmethod
    def _stencil_unknown_extent(cls, meta_arg):
        '''The field entry has a stencil access.

        :param meta_arg: the metadata associated with a field argument \
            with a stencil access.
        :type meta_arg: \
            :py:class:`psyclone.domain.lfric.kernel.FieldArgMetadata`

        '''

    @classmethod
    def _stencil_unknown_direction(cls, meta_arg):
        '''The field entry stencil access is of type XORY1D.

        :param meta_arg: the metadata associated with a field argument \
            with a xory1d stencil access.
        :type meta_arg: \
            :py:class:`psyclone.domain.lfric.kernel.FieldArgMetadata`

        '''

    @classmethod
    def _stencil_2d(cls, meta_arg):
        '''Stencil information that is passed from the Algorithm layer if the
        stencil is 'cross2d'.

        :param meta_arg: the metadata associated with a field argument \
            with a stencil access.
        :type meta_arg: \
            :py:class:`psyclone.domain.lfric.kernel.FieldArgMetadata`

        '''

    @classmethod
    def _stencil(cls, meta_arg):
        '''Stencil information that is passed from the Algorithm layer if the
        stencil is not 'cross2d'.

        :param meta_arg: the metadata associated with a field argument \
            with a stencil access.
        :type meta_arg: \
            :py:class:`psyclone.domain.lfric.kernel.FieldArgMetadata`

        '''

    @classmethod
    def _banded_dofmap(cls, function_space, cma_operator):
        '''Adds a banded dofmap for the provided function space and cma
        operator when there is an assembly cma kernel.

        :param str function_space: the function space for this banded \
            dofmap.
        :param cma_operator: the cma operator metadata associated with \
            this banded dofmap.
        :type cma_operator: :py:class:`psyclone.domain.lfric.kernel.\
            ColumnwiseOperatorArgMetadata`

        '''

    @classmethod
    def _indirection_dofmap(cls, function_space, cma_operator):
        '''Adds an indirection dofmap for the provided function space and cma
        operator when there is an apply cma kernel.

        :param str function_space: the function space for this \
            indirection dofmap.
        :param cma_operator: the cma operator metadata associated with \
            this indirection dofmap.
        :type cma_operator: :py:class:`psyclone.domain.lfric.kernel.\
            ColumnwiseOperatorArgMetadata`

        '''

    # pylint: disable=unidiomatic-typecheck
    @classmethod
    def _generate(cls, metadata):
        '''Specifies which arguments appear in an argument list and their
        ordering. Calls methods for each type of argument that can be
        specialised by a child class for its particular need.

        :param metadata: the LFRic kernel metadata.
        :type metadata: \
            py:class:`psyclone.domain.lfric.kernel.LFRicKernelMetadata`

        :raises InternalError: if an unexpected mesh property is found.

        '''
        # All operator types require the cell index to be provided
        if metadata.meta_args_get(
                [OperatorArgMetadata, ColumnwiseOperatorArgMetadata]):
            cls._cell_position()

        # Pass the number of layers in the mesh unless this kernel is
        # applying a CMA operator or doing a CMA matrix-matrix calculation
        if metadata.kernel_type not in ["cma-apply", "cma-matrix-matrix"]:
            cls._mesh_height()

        # Pass the number of cells in the mesh if this kernel has a
        # LMA operator argument
        # TODO this code should replace the code that currently includes
        # this quantity for *every* operator it encounters.
        # if metadata.meta_args_get(OperatorArgMetadata):
        #     cls._mesh_ncell3d()

        # Pass the number of columns in the mesh if this kernel operates on
        # the 'domain' or has a CMA operator argument. For the former we
        # exclude halo columns.
        if metadata.operates_on == "domain":
            cls._mesh_ncell2d_no_halos()
        if metadata.meta_args_get(ColumnwiseOperatorArgMetadata):
            cls._mesh_ncell2d()

        if metadata.kernel_type == "inter-grid":
            # Inter-grid kernels require special arguments.  The
            # cell-map for the current column providing the mapping
            # from the coarse to the fine mesh.
            cls._cell_map()

        # For each argument in the order they are specified in the
        # kernel metadata, call particular methods depending on what
        # type of argument we find (field, field vector, operator or
        # scalar). If the argument is a field or field vector and also
        # has a stencil access then also call appropriate stencil
        # methods.
        const = LFRicConstants()
        for meta_arg in metadata.meta_args:

            if type(meta_arg) in [
                    FieldArgMetadata, FieldVectorArgMetadata,
                    InterGridArgMetadata, InterGridVectorArgMetadata]:
                if type(meta_arg) in [FieldArgMetadata, InterGridArgMetadata]:
                    cls._field(meta_arg)
                if type(meta_arg) in [
                        FieldVectorArgMetadata, InterGridVectorArgMetadata]:
                    cls._field_vector(meta_arg)
                if meta_arg.stencil:
                    if meta_arg.stencil == "cross2d":
                        # stencil extent is not provided in the
                        # metadata so must be passed from the Algorithm
                        # layer.
                        cls._stencil_2d_unknown_extent(meta_arg)
                        # Due to the nature of the stencil extent array
                        # the max size of a stencil branch must be passed
                        # from the Algorithm layer.
                        cls._stencil_2d_max_extent(meta_arg)
                    else:
                        # stencil extent is not provided in the
                        # metadata so must be passed from the Algorithm
                        # layer.
                        cls._stencil_unknown_extent(meta_arg)
                    if meta_arg.stencil == "xory1d":
                        # if "xory1d is specified then the actual
                        # direction must be passed from the Algorithm layer.
                        cls._stencil_unknown_direction(meta_arg)
                    # stencil information that is always passed from the
                    # Algorithm layer.
                    if meta_arg.stencil == "cross2d":
                        cls._stencil_2d(meta_arg)
                    else:
                        cls._stencil(meta_arg)
            elif type(meta_arg) == OperatorArgMetadata:
                cls._operator(meta_arg)
            elif type(meta_arg) == ColumnwiseOperatorArgMetadata:
                cls._cma_operator(meta_arg)
            elif type(meta_arg) == ScalarArgMetadata:
                cls._scalar(meta_arg)
            else:
                raise InternalError(
                    f"Unexpected meta_arg type '{type(meta_arg).__name__}' "
                    f"found.")

        # For each unique function space (in the order they appear in the
        # metadata arguments)
        function_space_args = metadata.meta_args_get(
            [FieldArgMetadata, FieldVectorArgMetadata,
             InterGridArgMetadata, InterGridVectorArgMetadata,
             OperatorArgMetadata, ColumnwiseOperatorArgMetadata])
        unique_function_spaces = []
        for arg in function_space_args:
            if type(arg) in [
                    OperatorArgMetadata, ColumnwiseOperatorArgMetadata]:
                if arg.function_space_to not in unique_function_spaces:
                    unique_function_spaces.append(arg.function_space_to)
                if arg.function_space_from not in unique_function_spaces:
                    unique_function_spaces.append(arg.function_space_from)
            else:
                if arg.function_space not in unique_function_spaces:
                    unique_function_spaces.append(arg.function_space)

        for function_space in unique_function_spaces:
            # Provide arguments common to LMA operators and fields on
            # a space *unless* this is an inter-grid or CMA
            # matrix-matrix kernel
            if metadata.kernel_type not in [
                    "cma-matrix-matrix", "inter-grid"]:
                cls._fs_common(function_space)

            # Provide additional arguments if there is a
            # field on this space
            if [arg for arg in metadata.meta_args_get(
                    [FieldArgMetadata, FieldVectorArgMetadata])
                    if arg.function_space == function_space]:
                cls._fs_compulsory_field(function_space)

            # Provide additional arguments if there is a
            # intergrid field on this space
            intergrid_field = [arg for arg in metadata.meta_args_get(
                [InterGridArgMetadata, InterGridVectorArgMetadata])
                               if arg.function_space == function_space]
            if intergrid_field:
                cls._fs_intergrid(intergrid_field[0])

            cma_ops = [arg for arg in metadata.meta_args_get(
                ColumnwiseOperatorArgMetadata) if function_space in [
                    arg.function_space_to, arg.function_space_from]]
            if cma_ops:
                if metadata.kernel_type == "cma-assembly":
                    # CMA-assembly requires banded dofmaps
                    cls._banded_dofmap(function_space, cma_ops[0])
                elif metadata.kernel_type == "cma-apply":
                    # Applying a CMA operator requires indirection dofmaps
                    cls._indirection_dofmap(
                        function_space, cma_ops[0])

            # Provide any optional arguments. These arguments are
            # associated with the keyword arguments (basis function
            # and differential basis function) for a function space.
            meta_funcs = metadata.meta_funcs \
                if metadata.meta_funcs else []
            if [func for func in meta_funcs if func.basis_function and
                    func.function_space == function_space]:
                cls._basis(function_space)
            if [func for func in meta_funcs if func.diff_basis_function
                    and func.function_space == function_space]:
                cls._diff_basis(function_space)

        # The boundary condition kernel (enforce_bc_kernel) is a
        # special case.
        if metadata.procedure_name and \
                metadata.procedure_name.lower() == "enforce_bc_code":
            cls._field_bcs_kernel()

        # The operator boundary condition kernel
        # (enforce_operator_bc_kernel) is a special case.
        if metadata.procedure_name and \
                metadata.procedure_name.lower() == "enforce_operator_bc_code":
            cls._operator_bcs_kernel()

        # Reference-element properties
        if metadata.meta_ref_element:
            cls._ref_element_properties(metadata.meta_ref_element)

        # Mesh properties
        if metadata.meta_mesh:
            cls._mesh_properties(metadata.meta_mesh)

        # Quadrature arguments are required if one or more basis or
        # differential basis functions are used by the kernel and a
        # quadrature shape is supplied.
        if metadata.meta_funcs and metadata.shapes and \
           [shape for shape in metadata.shapes if shape in
                const.VALID_QUADRATURE_SHAPES]:
            cls._quad_rule(metadata.shapes)
