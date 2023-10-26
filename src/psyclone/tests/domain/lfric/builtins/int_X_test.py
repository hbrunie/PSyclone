# -----------------------------------------------------------------------------
# BSD 3-Clause License
#
# Copyright (c) 2017-2023, Science and Technology Facilities Council.
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
# Modified: I. Kavcic, Met Office
# Modified: R. W. Ford and N. Nobre, STFC Daresbury Lab
# Modified: by J. Henrichs, Bureau of Meteorology

''' Module containing pytest tests of the LFRicIntXKern built-in
    (converting real to integer field elements).'''

import os
import pytest

from psyclone.configuration import Config
from psyclone.domain.lfric.kernel import LFRicKernelMetadata
from psyclone.domain.lfric.lfric_builtins import LFRicIntXKern
from psyclone.parse.algorithm import parse
from psyclone.psyGen import PSyFactory
from psyclone.psyir.nodes import Loop
from psyclone.tests.lfric_build import LFRicBuild


# Constants
BASE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))),
    "test_files", "dynamo0p3")

# The PSyclone API under test
API = "dynamo0.3"


def test_int_X(tmpdir, monkeypatch, annexed, dist_mem):
    '''Test that 1) the '__str__' method of 'LFRicIntXKern' returns the
    expected string and 2) we generate correct code for the built-in
    operation 'Y = int(X, i_def)' where 'Y' is an integer-valued
    field, 'X' is the real-valued field being converted and the
    correct kind, 'i_def', is picked up from the associated
    field. Test with and without annexed DoFs being computed as this
    affects the generated code. 3) Also test the 'metadata()' method.

    '''
    metadata = LFRicIntXKern.metadata()
    assert isinstance(metadata, LFRicKernelMetadata)
    api_config = Config.get().api_conf(API)
    monkeypatch.setattr(api_config, "_compute_annexed_dofs", annexed)
    _, invoke_info = parse(os.path.join(BASE_PATH,
                                        "15.10.3_int_X_builtin.f90"),
                           api=API)
    psy = PSyFactory(API, distributed_memory=dist_mem).create(invoke_info)
    # Test '__str__' method
    first_invoke = psy.invokes.invoke_list[0]
    kern = first_invoke.schedule.children[0].loop_body[0]
    assert str(kern) == ("Built-in: int_X (convert a real-valued to an "
                         "integer-valued field)")
    # Test code generation
    code = str(psy.gen)

    assert LFRicBuild(tmpdir).code_compiles(psy)

    # First check that the correct field types and constants are used
    output = (
        "    USE constants_mod, ONLY: r_def, i_def\n"
        "    USE field_mod, ONLY: field_type, field_proxy_type\n"
        "    USE integer_field_mod, ONLY: integer_field_type, "
        "integer_field_proxy_type\n")
    assert output in code

    if not dist_mem:
        output = (
            "      INTEGER(KIND=i_def), pointer, dimension(:) :: f2_data => "
            "null()\n"
            "      TYPE(integer_field_proxy_type) f2_proxy\n"
            "      REAL(KIND=r_def), pointer, dimension(:) :: f1_data => "
            "null()\n"
            "      TYPE(field_proxy_type) f1_proxy\n"
            "      INTEGER(KIND=i_def) undf_aspc1_f2\n"
            "      !\n"
            "      ! Initialise field and/or operator proxies\n"
            "      !\n"
            "      f2_proxy = f2%get_proxy()\n"
            "      f2_data => f2_proxy%data\n"
            "      f1_proxy = f1%get_proxy()\n"
            "      f1_data => f1_proxy%data\n"
            "      !\n"
            "      ! Initialise number of DoFs for aspc1_f2\n"
            "      !\n"
            "      undf_aspc1_f2 = f2_proxy%vspace%get_undf()\n"
            "      !\n"
            "      ! Set-up all of the loop bounds\n"
            "      !\n"
            "      loop0_start = 1\n"
            "      loop0_stop = undf_aspc1_f2\n"
            "      !\n"
            "      ! Call our kernels\n"
            "      !\n"
            "      DO df=loop0_start,loop0_stop\n"
            "        f2_data(df) = int(f1_data(df), i_def)\n"
            "      END DO\n"
            "      !\n"
            "    END SUBROUTINE invoke_0\n")
        assert output in code
    else:
        output_dm_2 = (
            "      loop0_stop = f2_proxy%vspace%get_last_dof_annexed()\n"
            "      !\n"
            "      ! Call kernels and communication routines\n"
            "      !\n"
            "      DO df=loop0_start,loop0_stop\n"
            "        f2_data(df) = int(f1_data(df), i_def)\n"
            "      END DO\n"
            "      !\n"
            "      ! Set halos dirty/clean for fields modified in the "
            "above loop\n"
            "      !\n"
            "      CALL f2_proxy%set_dirty()\n"
            "      !\n")
        if not annexed:
            output_dm_2 = output_dm_2.replace("dof_annexed", "dof_owned")
        assert output_dm_2 in code


def test_int_X_precision(monkeypatch):
    '''Test that the built-in picks up and creates correct code for a
    scalar with precision that is not the default i.e. not 'i_def'. At
    the moment there is no other integer precision so we make one up
    and use monkeypatch to get round any error checks. However, this
    does mean that we can't check whether it compiles. 3) Also test
    the 'metadata()' method.

    '''
    _, invoke_info = parse(os.path.join(BASE_PATH,
                                        "15.10.3_int_X_builtin.f90"),
                           api=API)
    psy = PSyFactory(API).create(invoke_info)
    # Test '__str__' method
    first_invoke = psy.invokes.invoke_list[0]
    kern = first_invoke.schedule.children[0].loop_body[0]
    monkeypatch.setattr(kern.args[0], "_precision", "i_solver")
    code = str(psy.gen)
    assert "USE constants_mod, ONLY: r_def, i_solver, i_def" in code
    assert "f2_data(df) = int(f1_data(df), i_solver)" in code


def test_int_X_lowering(fortran_writer):
    '''
    Test that the lower_to_language_level() method works as expected.

    '''
    _, invoke_info = parse(os.path.join(BASE_PATH,
                                        "15.10.3_int_X_builtin.f90"),
                           api=API)
    psy = PSyFactory(API,
                     distributed_memory=False).create(invoke_info)
    first_invoke = psy.invokes.invoke_list[0]
    kern = first_invoke.schedule.children[0].loop_body[0]
    #kern.lower_to_language_level()
    #loop = first_invoke.schedule.walk(Loop)[0]
    #code = fortran_writer(loop)
    #assert ("do df = loop0_start, loop0_stop, 1\n"
    #        "  asum = asum + f1_data(df)\n"
    #        "enddo") in code
