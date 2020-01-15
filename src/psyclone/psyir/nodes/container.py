# -----------------------------------------------------------------------------
# BSD 3-Clause License
#
# Copyright (c) 2017-2020, Science and Technology Facilities Council.
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

''' This module contains the container node implementation'''

from psyclone.psyir.nodes import Node
from psyclone.psyir.symbols import SymbolTable

class Container(Node):
    '''Node representing a set of KernelSchedule and/or Container nodes,
    as well as a name and a SymbolTable. This construct can be used to
    scope symbols of variables, KernelSchedule names and Container
    names. In Fortran a container would naturally represent a module
    or a submodule.

    :param str name: the name of the container.
    :param parent: optional parent node of this Container in the PSyIR.
    :type parent: :py:class:`psyclone.psyGen.Node`

    '''
    def __init__(self, name, parent=None):
        super(Container, self).__init__(parent=parent)
        self._name = name
        self._symbol_table = SymbolTable(self)

    @staticmethod
    def create(name, symbol_table, children):
        '''Create a Container instance given a name, a symbol table and a
        list of child nodes.

        :param str name: the name of the Container.
        :param symbol_table: the symbol table associated with this \
            Container.
        :type symbol_table: :py:class:`psyclone.psyGen.SymbolTable`
        :param children: a list of PSyIR nodes contained in the \
            Container. These must be Containers or KernelSchedules.
        :type children: list of :py:class:`psyclone.psyGen.Container` \
            or :py:class:`psyclone.psyGen.KernelSchedule`

        :returns: a Container instance.
        :rtype: :py:class:`psyclone.psyGen.Container`

        :raises GenerationError: if the arguments to the create method \
            are not of the expected type.

        '''
        from psyclone.psyGen import GenerationError, KernelSchedule
        if not isinstance(name, str):
            raise GenerationError(
                "name argument in create method of Container class "
                "should be a string but found '{0}'."
                "".format(type(name).__name__))
        if not isinstance(symbol_table, SymbolTable):
            raise GenerationError(
                "symbol_table argument in create method of Container class "
                "should be a SymbolTable but found '{0}'."
                "".format(type(symbol_table).__name__))
        if not isinstance(children, list):
            raise GenerationError(
                "children argument in create method of Container class "
                "should be a list but found '{0}'."
                "".format(type(children).__name__))
        for child in children:
            if not isinstance(child, (KernelSchedule, Container)):
                raise GenerationError(
                    "child of children argument in create method of "
                    "Container class should be a PSyIR KernelSchedule or "
                    "Container but found '{0}'.".format(type(child).__name__))

        container = Container(name)
        container._symbol_table = symbol_table
        symbol_table._schedule = container
        for child in children:
            child.parent = container
        container.children = children
        return container

    @property
    def name(self):
        '''
        :returns: name of the container.
        :rtype: str

        '''
        return self._name

    @name.setter
    def name(self, new_name):
        '''Sets a new name for the container.

        :param str new_name: new name for the container.

        '''
        self._name = new_name

    @property
    def symbol_table(self):
        '''
        :returns: table containing symbol information for the container.
        :rtype: :py:class:`psyclone.psyir.symbols.SymbolTable`

        '''
        return self._symbol_table

    def node_str(self, colour=True):
        '''
        Returns the name of this node with appropriate control codes
        to generate coloured output in a terminal that supports it.

        :param bool colour: whether or not to include colour control codes.

        :returns: description of this node, possibly coloured.
        :rtype: str
        '''
        return self.coloured_name(colour) + "[{0}]".format(self.name)

    def __str__(self):
        return "Container[{0}]\n".format(self.name)



