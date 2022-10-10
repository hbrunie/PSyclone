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
# Author: A. R. Porter, STFC Daresbury Lab


''' Performs pytest tests on the support for allocate statements in the
    fparser2 PSyIR front-end. '''


from psyclone.psyir.nodes import (ArrayReference, IntrinsicCall, Literal,
                                  Range, Reference, UnaryOperation)


def test_basic_allocate(fortran_reader):
    '''Check that a basic allocate is correctly captured by the frontend.'''
    code = '''
program test_alloc
  integer, parameter :: ndof = 8
  real, allocatable, dimension(:, :) :: var1
  allocate(var1(10, ndof))
end program test_alloc
'''
    psyir = fortran_reader.psyir_from_source(code)
    calls = psyir.walk(IntrinsicCall)
    assert len(calls) == 1
    call = calls[0]
    assert len(call.children) == 1
    assert isinstance(call.children[0], ArrayReference)
    assert isinstance(call.children[0].children[0], Range)
    assert isinstance(call.children[0].children[0].stop, Literal)
    assert isinstance(call.children[0].children[1].stop, Reference)


def test_alloc_with_stat(fortran_reader):
    '''Check that an allocate with a status argument is correctly handled.'''
    code = '''
program test_alloc
  integer, parameter :: ndof = 8
  integer :: ierr
  real, allocatable, dimension(:, :) :: var1
  allocate(var1(10, ndof), stat=ierr)
end program test_alloc
'''
    psyir = fortran_reader.psyir_from_source(code)
    calls = psyir.walk(IntrinsicCall)
    assert len(calls) == 1
    # The call should have a named argument.
    assert calls[0].argument_names == [None, "STAT"]
    assert isinstance(calls[0].children[1], Reference)
    assert calls[0].children[1].symbol.name == "ierr"


def test_alloc_with_bounds(fortran_reader):
    '''
    Check that an allocate which specifies the lower bounds of the array is
    handled correctly.

    '''
    code = '''
program test_alloc
  integer, parameter :: ndof = 8
  integer :: ierr
  real, allocatable, dimension(:, :) :: var1
  allocate(var1(2:10, -1:ndof))
end program test_alloc
'''
    psyir = fortran_reader.psyir_from_source(code)
    calls = psyir.walk(IntrinsicCall)
    assert len(calls) == 1
    aref = calls[0].children[0]
    assert isinstance(aref, ArrayReference)
    print(aref.view())
    assert aref.indices[0].start.value == "2"
    assert isinstance(aref.indices[1].start, UnaryOperation)
    assert aref.indices[1].stop.name == "ndof"
