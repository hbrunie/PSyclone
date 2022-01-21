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
# Authors R. W. Ford, A. R. Porter and S. Siso, STFC Daresbury Lab
# Modified I. Kavcic and A. Coughtrie, Met Office
# Modified J. Henrichs, Bureau of Meteorology

'''This module implements a class that manages all of the data references
that must be copied over to a GPU before executing the kernel. Ordering
of the parameters does not matter apart from where we have members of
derived types. In that case, the derived type itself must be specified
first before any members.
'''

from psyclone.domain.lfric import ArgOrdering, LFRicConstants
from psyclone.psyir.symbols import (ArrayType, ScalarType, DataSymbol,
                                    DataTypeSymbol, DeferredType,
                                    ContainerSymbol, ImportInterface)


class KernCallInvokeArgList(ArgOrdering):
    '''Determines the arguments that must be provided to an `invoke` of a
    kernel, according to that kernel's metadata.

    :param kern: the kernel object for which to determine arguments.
    :type kern: :py:class:`psyclone.dynamo0p3.DynKern`
    :param symbol_table: TBD
    :type symbol_table: TBD

    '''
    def __init__(self, kern, symbol_table):
        super().__init__(kern)
        self._symtab = symbol_table
        self._fields = []
        self._scalars = []
        self._qr_objects = []

    @property
    def fields(self):
        '''
        :returns: the field (and field-vector) arguments to the kernel.
        :rtype: list of :py:class:`psyclone.psyir.symbols.DataSymbol`
        '''
        return self._fields

    @property
    def scalars(self):
        '''
        :returns: the scalar arguments to the kernel.
        :rtype: list of :py:class:`psyclone.psyir.symbols.DataSymbol`
        '''
        return self._scalars

    @property
    def quadrature_objects(self):
        ''' TODO '''
        return self._qr_objects

    def generate(self, var_accesses=None):
        ''' Just ensures that our internal lists of field and scalar arguments
        are reset (as calling generate() populates them) before calling this
        method in the parent class.

        :param var_accesses: TBD
        '''
        self._fields = []
        self._scalars = []
        super().generate(var_accesses)

    def scalar(self, scalar_arg, var_accesses=None):
        ''' '''
        super().scalar(scalar_arg, var_accesses)

        # Create a DataSymbol for this kernel argument.
        if scalar_arg.intrinsic_type == "real":
            datatype = ScalarType(ScalarType.Intrinsic.REAL,
                                  self._symtab.lookup("r_def"))
        elif scalar_arg.intrinsic_type == "integer":
            datatype = ScalarType(ScalarType.Intrinsic.INTEGER,
                                  self._symtab.lookup("i_def"))
        else:
            raise NotImplementedError(
                f"Scalar of type '{scalar_arg.data_type}' not supported.")

        sym = self._symtab.new_symbol(scalar_arg.name,
                                      symbol_type=DataSymbol,
                                      datatype=datatype)
        self._scalars.append(sym)

    def fs_common(self, function_space, var_accesses=None):
        ''' Nothing '''

    def field_vector(self, argvect, var_accesses=None):
        '''Add the field vector associated with the argument 'argvect' to the
        argument list. OpenACC requires the field and the
        dereferenced data to be specified. If supplied it also stores
        this access in var_accesses.

        :param argvect: the field vector to add.
        :type argvect: :py:class:`psyclone.dynamo0p3.DynKernelArgument`
        :param var_accesses: optional VariablesAccessInfo instance to store \
            the information about variable accesses.
        :type var_accesses: \
            :py:class:`psyclone.core.access_info.VariablesAccessInfo`

        '''
        ftype = self._symtab.lookup("field_type")
        dtype = ArrayType(ftype, [argvect.vector_size])

        sym = self._symtab.new_symbol(argvect.name,
                                      symbol_type=DataSymbol, datatype=dtype)
        self._fields.append(sym)
        self.append(sym.name)

    def field(self, arg, var_accesses=None):
        '''Add the field array associated with the argument 'arg' to the
        argument list. OpenACC requires the field and the
        dereferenced data to be specified. If supplied it also
        stores this access in var_accesses.

        :param arg: the field to be added.
        :type arg: :py:class:`psyclone.dynamo0p3.DynKernelArgument`
        :param var_accesses: optional VariablesAccessInfo instance to store \
            the information about variable accesses.
        :type var_accesses: \
            :py:class:`psyclone.core.access_info.VariablesAccessInfo`

        '''
        ftype = self._symtab.lookup("field_type")
        sym = self._symtab.new_symbol(arg.name,
                                      symbol_type=DataSymbol, datatype=ftype)
        self._fields.append(sym)
        self.append(sym.name)

    def stencil(self, arg, var_accesses=None):
        '''Add general stencil information associated with the argument 'arg'
        to the argument list. OpenACC requires the full dofmap to be
        specified. If supplied it also stores this access in var_accesses.

        :param arg: the meta-data description of the kernel \
            argument with which the stencil is associated.
        :type arg: :py:class:`psyclone.dynamo0p3.DynKernelArgument`
        :param var_accesses: optional VariablesAccessInfo instance to store \
            the information about variable accesses.
        :type var_accesses: \
            :py:class:`psyclone.core.access_info.VariablesAccessInfo`

        '''
        # Import here to avoid circular dependency
        # pylint: disable=import-outside-toplevel
        from psyclone.dynamo0p3 import DynStencils
        var_name = DynStencils.dofmap_name(self._kern.root.symbol_table, arg)
        self.append(var_name, var_accesses)

    def stencil_2d(self, arg, var_accesses=None):
        '''Add general 2D stencil information associated with the argument
        'arg' to the argument list. OpenACC requires the full dofmap to be
        specified. If supplied it also stores this access in var_accesses.This
        method passes through to the stencil method.

        :param arg: the meta-data description of the kernel \
            argument with which the stencil is associated.
        :type arg: :py:class:`psyclone.dynamo0p3.DynKernelArgument`
        :param var_accesses: optional VariablesAccessInfo instance to store \
            the information about variable accesses.
        :type var_accesses: \
            :py:class:`psyclone.core.access_info.VariablesAccessInfo`

        '''
        self.stencil(arg, var_accesses)

    def stencil_unknown_extent(self, arg, var_accesses=None):
        '''Add stencil information to the argument list associated with the
        argument 'arg' if the extent is unknown. If supplied it also stores
        this access in var_accesses.

        :param arg: the kernel argument with which the stencil is associated.
        :type arg: :py:class:`psyclone.dynamo0p3.DynKernelArgument`
        :param var_accesses: optional VariablesAccessInfo instance to store \
            the information about variable accesses.
        :type var_accesses: \
            :py:class:`psyclone.core.access_info.VariablesAccessInfo`

        '''
        # The extent is not specified in the metadata so pass the value in
        # Import here to avoid circular dependency
        # pylint: disable=import-outside-toplevel
        from psyclone.dynamo0p3 import DynStencils
        name = DynStencils.dofmap_size_name(self._kern.root.symbol_table, arg)
        self.append(name, var_accesses)

    def stencil_2d_unknown_extent(self, arg, var_accesses=None):
        '''Add 2D stencil information to the argument list associated with the
        argument 'arg' if the extent is unknown. If supplied it also stores
        this access in var_accesses. This method passes through to the
        stencil_unknown_extent method.

        :param arg: the kernel argument with which the stencil is associated.
        :type arg: :py:class:`psyclone.dynamo0p3.DynKernelArgument`
        :param var_accesses: optional VariablesAccessInfo instance to store \
            the information about variable accesses.
        :type var_accesses: \
            :py:class:`psyclone.core.access_info.VariablesAccessInfo`

        '''
        self.stencil_unknown_extent(arg, var_accesses)

    def operator(self, arg, var_accesses=None):
        '''Add the operator argument. If supplied it also stores this access
        in var_accesses.

        :param arg: the meta-data description of the operator.
        :type arg: :py:class:`psyclone.dynamo0p3.DynKernelArgument`
        :param var_accesses: optional VariablesAccessInfo instance to store \
            the information about variable accesses.
        :type var_accesses: \
            :py:class:`psyclone.core.access_info.VariablesAccessInfo`

        '''
        self.append(arg.name, var_accesses)

    def fs_compulsory_field(self, function_space, var_accesses=None):
        '''Add compulsory arguments associated with this function space to
        the list. Since these are only added in the PSy layer, there's nothing
        to do at the Algorithm layer.

        :param function_space: the function space for which the compulsory \
            arguments are added.
        :type function_space: :py:class:`psyclone.domain.lfric.FunctionSpace`
        :param var_accesses: optional VariablesAccessInfo instance to store \
            the information about variable accesses.
        :type var_accesses: \
            :py:class:`psyclone.core.access_info.VariablesAccessInfo`

        '''

    def quad_rule(self, var_accesses=None):
        '''Add quadrature-related information to the kernel argument list.
        Adds the necessary arguments to the argument list, and optionally
        adds variable access information to the var_accesses object.

        :param var_accesses: optional VariablesAccessInfo instance to store \
            the information about variable accesses.
        :type var_accesses: \
            :py:class:`psyclone.core.access_info.VariablesAccessInfo`

        '''
        lfric_const = LFRicConstants()
        #use finite_element_config_mod,      only: element_order

        #fe_config_mod = self._symtab.new_symbol("finite_element_config_mod",
        #                                        symbol_type=ContainerSymbol)
        #self._symtab.new_symbol("element_order", symbol_type=DataSymbol,
        #                        datatype=DeferredType(),
        #                        interface=ImportInterface(fe_config_mod))
        try:
            qr_rule_sym = self._symtab.lookup("quadrature_rule")
        except KeyError:
            qr_gaussian_mod = self._symtab.new_symbol(
                "quadrature_rule_gaussian_mod", symbol_type=ContainerSymbol)
            qr_gaussian_type = self._symtab.new_symbol(
                "quadrature_rule_gaussian_type", symbol_type=DataTypeSymbol,
                datatype=DeferredType(),
                interface=ImportInterface(qr_gaussian_mod))
            qr_rule_sym = self._symtab.new_symbol("quadrature_rule",
                                                  symbol_type=DataSymbol,
                                                  datatype=qr_gaussian_type)

        for shape, rule in self._kern.qr_rules.items():
            mod_name = lfric_const.QUADRATURE_TYPE_MAP[shape]["module"]
            type_name = lfric_const.QUADRATURE_TYPE_MAP[shape]["type"]
            try:
                quad_container = self._symtab.lookup(mod_name)
            except KeyError:
                quad_container = self._symtab.new_symbol(
                    mod_name, symbol_type=ContainerSymbol)
            try:
                quad_type = self._symtab.lookup(type_name)
            except KeyError:
                quad_type = self._symtab.new_symbol(
                    type_name, symbol_type=DataTypeSymbol,
                    datatype=DeferredType(),
                    interface=ImportInterface(quad_container))
            sym = self._symtab.new_symbol(rule.psy_name,
                                          symbol_type=DataSymbol,
                                          datatype=quad_type)
            self._qr_objects.append((sym, shape))
            self.append(sym.name)


# ============================================================================
# For automatic documentation creation:
__all__ = ["KernCallInvokeArgList"]
