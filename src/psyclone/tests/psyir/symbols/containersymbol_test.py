# -----------------------------------------------------------------------------
# BSD 3-Clause License
#
# Copyright (c) 2017-2019, Science and Technology Facilities Council.
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

''' Perform py.test tests on the psygen.psyir.symbols.containersymbols file '''

import pytest
from psyclone.psyir.symbols import ContainerSymbol, SymbolError
from psyclone.psyir.symbols.containersymbol import ContainerSymbolInterface, \
    FortranModuleInterface
from psyclone.psyGen import Container
from psyclone.configuration import Config


def test_containersymbol_initialisation():
    '''Test that a ContainerSymbol instance can be created when valid
    arguments are given, otherwise raise relevant exceptions.'''

    sym = ContainerSymbol("my_mod")
    assert isinstance(sym, ContainerSymbol)
    assert sym.name == "my_mod"
    assert not sym._reference  # Reference are not evaluated until told
    # Right now the FortranModuleInterface is assigned by default
    # because it is the only one. This may change in the future
    assert sym._interface == FortranModuleInterface

    with pytest.raises(TypeError) as error:
        sym = ContainerSymbol(None)
    assert "ContainerSymbol name attribute should be of type 'str'" \
        in str(error)


def test_containersymbol_str():
    '''Test that a ContainerSymbol instance can be stringified'''

    sym = ContainerSymbol("my_mod")
    assert str(sym) == "my_mod: <not linked>"

    sym._reference = Container("my_mod")
    assert str(sym) == "my_mod: <linked>"


def test_containersymbol_generic_interface():
    '''Check ContainerSymbolInterface abstract methods '''

    abstractinterface = ContainerSymbolInterface

    with pytest.raises(NotImplementedError) as error:
        abstractinterface.import_container("name")
    assert "Abstract method" in str(error)


def test_containersymbol_fortranmodule_interface():
    '''Check that the FortranModuleInterface imports Fortran modules
    as containers or produces the appropriate errors'''
    import os

    fminterface = FortranModuleInterface

    # Try with an unexistant module and no include path
    Config.get().include_paths = []
    with pytest.raises(SymbolError) as error:
        fminterface.import_container("fake_module")
    assert ("Module fake_module.f90 not found in any of the include_path "
            "directories []." in str(error))

    # Try with an unexistant module and a directory in the include path
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "test_files")
    Config.get().include_paths = [path]
    with pytest.raises(SymbolError) as error:
        fminterface.import_container("fake_module")
    assert ("Module fake_module.f90 not found in any of the include_path "
            "directories ['" in str(error))

    # Try importing and existant Fortran module
    container = fminterface.import_container("dummy_module")
    assert isinstance(container, Container)
    assert container.name == "dummy_module"
