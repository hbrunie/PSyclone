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
# Author J. Henrichs, Bureau of Meteorology

'''This module contains the RoutineInfo class, which is used to store
and cache information about a routine (i.e. a subroutine or a function) in a
module.
'''

from fparser.two.Fortran2003 import Function_Subprogram

from psyclone.psyir.nodes import (Call, Container, Reference)
from psyclone.psyir.symbols import (ArgumentInterface, ImportInterface,
                                    RoutineSymbol)


# ============================================================================
class RoutineInfo:
    '''This class stores information about a routine (function, subroutine).

    :param str name: the module name.
    :param str filename: the name of the source file that stores this module \
        (including path).

    '''

    def __init__(self, module_info, ast):
        self._module_info = module_info
        self._ast = ast
        self._name = str(ast.content[0].items[1])

        self._non_locals = None

        self._psyir = None

    # -------------------------------------------------------------------------
    @property
    def name(self):
        ''':returns: the name of the routine.
        :rtype: str

        '''
        return self._name

    # -------------------------------------------------------------------------
    def set_psyir(self, psyir):
        '''Sets the PSyIR representation of this routine. This is called from
        the module info object that this object is managed by.

        :param psyir: the PSyIR of this routine.
        :type psyir: :py:class:`psyclone.psyir.nodes.Node`

        '''
        self._psyir = psyir

    # ------------------------------------------------------------------------
    @staticmethod
    def _compute_non_locals_references(access, sym):
        '''This function analyses if the symbol is a local variable, or if
        it was declared in the container, which is considered a non-local
        access. The symbol's interface is LocalInterface in any case.
        So we need to identify the symbol table in which the symbol is
        actually declared, and check if it is declared in the routine, or
        further up in the tree in the container (i.e. module).
        # TODO #1089: this should simplify the implementation.

        '''
        node = access
        while node:
            # A routine has its own name as a symbol in its symbol table.
            # That reference is not useful to decide what kind of symbol
            # it is (i.e. does it belong to this routine's container, in
            # which case it is a non-local access)
            if hasattr(node, "_symbol_table") and \
                    sym.name in node.symbol_table and node.name != sym.name:
                existing_sym = node.symbol_table.lookup(sym.name)
                if isinstance(node, Container):
                    # It is a variable from the module in which the
                    # current function is, so it is a non-local access
                    if isinstance(existing_sym, RoutineSymbol):
                        return ("routine", node.name, sym.name)
                    return ("reference", node.name, sym.name)

            # Otherwise keep on looking
            node = node.parent
        return None

    # ------------------------------------------------------------------------
    def _compute_all_non_locals(self):
        # pylint: disable=too-many-branches
        '''This function computes and caches all non-local access of this
        routine.

        '''
        # Circular dependency
        # pylint: disable=import-outside-toplevel
        from psyclone.psyGen import BuiltIn, Kern

        self._non_locals = []

        if not self._psyir:
            # Parsing the PSyIR in the parent will populate the PSyIR
            # information for each subroutine and function.
            self._module_info.get_psyir()

        for access in self._psyir.walk((Kern, Call, Reference)):
            # Builtins are certainly not externals, so ignore them.
            if isinstance(access, BuiltIn):
                continue

            if isinstance(access, Kern):
                # A kernel is a subroutine call from a module:
                self._non_locals.append(("routine", access.module_name,
                                         access.name))
                continue

            if isinstance(access, Call):
                sym = access.routine
                if isinstance(sym.interface, ImportInterface):
                    module_name = sym.interface.container_symbol.name
                    self._non_locals.append(("routine", module_name,
                                             sym.name))
                    continue
                # No import. This could either be a subroutine from
                # this module, or just a global function.
                try:
                    self._module_info.get_routine_info(sym.name)
                    # A local function that is in the same module:
                    self._non_locals.append(("routine",
                                             self._module_info.name, sym.name))
                except KeyError:
                    # We don't know where the subroutine comes from
                    self._non_locals.append(("routine", None, sym.name))

                continue

            # Now it's either a variable, or a function call (TODO #1314):
            sym = access.symbol
            if isinstance(sym.interface, ArgumentInterface):
                # Arguments are not external symbols and can be ignored
                continue

            if isinstance(sym.interface, ImportInterface):
                # It is imported, record the information. The type needs
                # to be identified when parsing the corresponding module:
                module_name = sym.interface.container_symbol.name
                self._non_locals.append(("unknown", module_name, sym.name))
                continue

            # Check for an assignment of a result in a function, which
            # does not need to be reported:
            if self._psyir.return_symbol and \
                    sym.name == self._psyir.return_symbol.name:
                continue

            info = self._compute_non_locals_references(access, sym)
            if info:
                self._non_locals.append(info)

    # ------------------------------------------------------------------------
    def get_non_local_symbols(self):
        '''This function returns a list of non-local accesses in the given
        routine. It returns a list of triplets, each one containing:
        - the type ('routine', 'function', 'reference', 'unknown').
          The latter is used for array references or function calls,
          which we cannot distinguish till #1314 is done.
        - the name of the module (lowercase). This can be 'None' if no
          module information is available.
        - the name of the symbol (lowercase)

        :param str routine_name: the name of the routine.

        :returns: the non-local accesses in the given routine.
        :rtype: List[Tuple[str, str, str]]

        :raises ModuleInfoError: if the given routine name is not defined \
            in this module.

        '''

        if self._non_locals is None:
            self._compute_all_non_locals()

        return self._non_locals
