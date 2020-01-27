# -----------------------------------------------------------------------------
# BSD 3-Clause License
#
# Copyright (c) 2019-2020, Science and Technology Facilities Council.
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
# Author: A. R. Porter, STFC Daresbury Lab


''' Performs py.test tests on the support for use statements in the fparser2
    PSyIR front-end '''

from __future__ import absolute_import
import pytest
from fparser.common.readfortran import FortranStringReader
from fparser.two import Fortran2003
from psyclone.psyir.frontend.fparser2 import Fparser2Reader
from psyclone.psyir.symbols import ContainerSymbol, SymbolError
from psyclone.psyGen import KernelSchedule, GenerationError


@pytest.mark.usefixtures("f2008_parser")
def test_use_stmt():
    ''' Check that SymbolTable entries are correctly created from
    module use statements. '''
    fake_parent = KernelSchedule("dummy_schedule")
    processor = Fparser2Reader()
    reader = FortranStringReader("use my_mod, only: some_var\n"
                                 "use this_mod\n"
                                 "use other_mod, only: var1, var2\n")
    fparser2spec = Fortran2003.Specification_Part(reader)
    processor.process_declarations(fake_parent, fparser2spec.content, [])

    symtab = fake_parent.symbol_table

    for module_name in ["my_mod", "this_mod", "other_mod"]:
        container = symtab.lookup(module_name)
        assert isinstance(container, ContainerSymbol)
        assert container.name == module_name
        # Container reference is not updated until explicitly requested
        assert not container._reference

    for var in ["some_var", "var1", "var2"]:
        assert symtab.lookup(var).name == var

    assert symtab.lookup("some_var").interface.container_symbol \
        == symtab.lookup("my_mod")
    assert symtab.lookup("var2").interface.container_symbol \
        == symtab.lookup("other_mod")


@pytest.mark.usefixtures("f2008_parser")
def test_use_stmt_error(monkeypatch):
    ''' Check that we raise the expected error if the parse tree representing
    a USE statement doesn't have the expected structure. '''
    fake_parent = KernelSchedule("dummy_schedule")
    processor = Fparser2Reader()
    reader = FortranStringReader("use my_mod, only: some_var\n"
                                 "use this_mod\n"
                                 "use other_mod, only: var1, var2\n")
    fparser2spec = Fortran2003.Specification_Part(reader)
    monkeypatch.setattr(fparser2spec.content[0], "items",
                        [None, "hello", None])
    with pytest.raises(GenerationError) as err:
        processor.process_declarations(fake_parent, fparser2spec.content, [])
    assert ("Expected the parse tree for a USE statement to contain 5 items "
            "but found 3 for 'hello'" in str(err.value))


@pytest.mark.usefixtures("f2008_parser")
def test_multi_use_stmt():
    ''' Check that we handle the case where different symbols are imported
    from a module in separate USE statements. '''
    fake_parent = KernelSchedule("dummy_schedule")
    processor = Fparser2Reader()
    reader = FortranStringReader("use my_mod, only: some_var\n"
                                 "use this_mod\n"
                                 "use my_mod, only: var1, var2\n"
                                 "use this_mod, only: var3\n")
    fparser2spec = Fortran2003.Specification_Part(reader)
    processor.process_declarations(fake_parent, fparser2spec.content, [])
    symtab = fake_parent.symbol_table
    csymbols = symtab.container_symbols
    # Although there are 4 use statements, there are only 2 modules
    assert len(csymbols) == 2
    my_mod = symtab.lookup("my_mod")
    assert not my_mod.wildcard_import
    # Check that we have accumulated all imports
    assert len(my_mod.imported_symbols) == 3
    names = [sym.name for sym in my_mod.imported_symbols]
    assert sorted(names) == ["some_var", "var1", "var2"]
    this_mod = symtab.lookup("this_mod")
    assert this_mod.wildcard_import
    names = [sym.name for sym in this_mod.imported_symbols]
    assert names == ["var3"]


@pytest.mark.usefixtures("f2008_parser")
def test_name_clash_use_stmt():
    ''' Check that we raise the expected error if we encounter a module
    with a name that's already taken in the Symbol Table. This is invalid
    Fortran but we need to test the error-handling in PSyclone. '''
    fake_parent = KernelSchedule("dummy_schedule")
    processor = Fparser2Reader()
    reader = FortranStringReader("use my_mod, only: some_var\n"
                                 "use some_var, only: var1, var2\n")
    fparser2spec = Fortran2003.Specification_Part(reader)
    with pytest.raises(SymbolError) as err:
        processor.process_declarations(fake_parent, fparser2spec.content, [])
    assert "Found a USE of module 'some_var' but the symbol" in str(err.value)


@pytest.mark.usefixtures("f2008_parser")
def test_use_no_only_list():
    ''' Check that we create the correct Symbol Table entry for a use
    statement that has an 'only' clause but no list of imported symbols. '''
    fake_parent = KernelSchedule("dummy_schedule")
    processor = Fparser2Reader()
    reader = FortranStringReader("use my_mod, only: some_var\n"
                                 "use some_mod, only:\n")
    fparser2spec = Fortran2003.Specification_Part(reader)
    processor.process_declarations(fake_parent, fparser2spec.content, [])
    some_mod = fake_parent.symbol_table.lookup("some_mod")
    assert not some_mod.wildcard_import
    assert some_mod.imported_symbols == []


@pytest.mark.usefixtures("f2008_parser")
def test_broken_use(monkeypatch):
    ''' Check that we raise the expected error if we encounter an unrecognised
    parse tree for a USE statement. '''
    fake_parent = KernelSchedule("dummy_schedule")
    processor = Fparser2Reader()
    reader = FortranStringReader("use some_mod, only:\n")
    fparser2spec = Fortran2003.Specification_Part(reader)
    # Break the parse tree so that instead of ", ONLY:" it has "hello"
    monkeypatch.setattr(
        fparser2spec.content[0], "items",
        [None, None, Fortran2003.Name('my_mod'), 'hello', None])
    with pytest.raises(NotImplementedError) as err:
        processor.process_declarations(fake_parent, fparser2spec.content, [])
    assert "unsupported USE statement: 'USE my_modhello'" in str(err.value)


@pytest.mark.usefixtures("f2008_parser")
def test_redundant_empty_only_list():
    ''' Check that we drop 'use's with an empty only list if they become
    redundant. #TODO #11 Check for appropriate logging messages here once
    logging is implemented. '''
    fake_parent = KernelSchedule("dummy_schedule")
    processor = Fparser2Reader()
    # Empty only-list followed by wildcard import
    reader = FortranStringReader("use mod1, only:\n"
                                 "use mod1\n")
    fparser2spec = Fortran2003.Specification_Part(reader)
    processor.process_declarations(fake_parent, fparser2spec.content, [])
    csym = fake_parent.symbol_table.lookup("mod1")
    assert csym.wildcard_import
    # Wildcard import followed by empty only-list
    reader = FortranStringReader("use mod2\n"
                                 "use mod2, only:\n")
    fparser2spec = Fortran2003.Specification_Part(reader)
    processor.process_declarations(fake_parent, fparser2spec.content, [])
    csym = fake_parent.symbol_table.lookup("mod2")
    assert csym.wildcard_import
    # Empty only-list followed by named import
    reader = FortranStringReader("use mod3, only:\n"
                                 "use mod3, only: fred\n")
    fparser2spec = Fortran2003.Specification_Part(reader)
    processor.process_declarations(fake_parent, fparser2spec.content, [])
    csym = fake_parent.symbol_table.lookup("mod3")
    assert not csym.wildcard_import
    assert csym.imported_symbols[0].name == "fred"
    # Named import followed by empty only-list
    reader = FortranStringReader("use mod4, only: bob\n"
                                 "use mod4, only:\n")
    fparser2spec = Fortran2003.Specification_Part(reader)
    processor.process_declarations(fake_parent, fparser2spec.content, [])
    csym = fake_parent.symbol_table.lookup("mod4")
    assert not csym.wildcard_import
    assert csym.imported_symbols[0].name == "bob"


def test_use_same_symbol():
    ''' Check that we handle the case where the same symbol is imported from
    different modules.
    #TODO #11 Once logging is added, check that we log an appropriate
    warning for this case.
    '''
    fake_parent = KernelSchedule("dummy_schedule")
    processor = Fparser2Reader()
    reader = FortranStringReader("use mod2, only: fred\n"
                                 "use mod3, only: fred\n")
    fparser2spec = Fortran2003.Specification_Part(reader)
    processor.process_declarations(fake_parent, fparser2spec.content, [])
    csym = fake_parent.symbol_table.lookup("mod2")
    assert csym.imported_symbols[0].name == "fred"
    csym = fake_parent.symbol_table.lookup("mod3")
    # mod3 will have an empty list of symbols as 'fred' is already imported
    # from mod2.
    assert not csym.imported_symbols


def test_use_local_symbol_error():
    ''' Check that we raise the expected error if we encounter an import of
    a symbol that is already declared to be local. '''
    from psyclone.psyir.symbols import DataSymbol, DataType, LocalInterface
    fake_parent = KernelSchedule("dummy_schedule")
    # In practise this situation is hard to trigger as USE statements must
    # come before local declarations. Therefore we manually add a symbol
    # to the table first.
    fake_parent.symbol_table.add(DataSymbol("fred", DataType.INTEGER,
                                            interface=LocalInterface()))
    processor = Fparser2Reader()
    reader = FortranStringReader("use mod2, only: fred\n")
    fparser2spec = Fortran2003.Specification_Part(reader)
    with pytest.raises(SymbolError) as err:
        processor.process_declarations(fake_parent, fparser2spec.content, [])
    assert "'fred' is imported from module 'mod2' but is" in str(err.value)
