#!/usr/bin/env python
# -----------------------------------------------------------------------------
# BSD 3-Clause License
#
# Copyright (c) 2018-2021, Science and Technology Facilities Council
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
# Authors: R. W. Ford, A. R. Porter and S. Siso, STFC Daresbury Lab

''' PSyclone transformation script showing the introduction of OpenMP
directives into Nemo code. '''

from __future__ import print_function
from psyclone.psyGen import TransInfo,Invoke
from psyclone.nemo import NemoKern, NemoInvokeSchedule,NemoInvokes,NemoInvoke


def trans(psy):
    ''' Add OpenMP Parallel Loop directives to Nemo loops over levels
    in the provided PSy-layer.

    :param psy: the PSy object which this script will transform.
    :type psy: :py:class:`psyclone.psyGen.PSy`
    :returns: the transformed PSy object.
    :rtype: :py:class:`psyclone.psyGen.PSy`

    '''
    omp_trans = TransInfo().get_trans_name('OMPParallelLoopTrans')

    #print(psy._container.view())
    #nemokerns = psy._container.walk(NemoKern)
    nemoinvokeschedule = psy._container.walk(NemoInvokeSchedule)
    nemoinvokes = psy._container.walk(NemoInvokes)
    nemoinvoke = psy._container.walk(NemoInvoke)
    print("Nemo Invoke Schedule found:")
    for nis in nemoinvokeschedule:
        print(nis.view())
    print("Nemo Invokes found:")
    for nis in nemoinvokes:
        print(nis.view())
    print("Nemo Invoke found:")
    for nis in nemoinvoke:
        print(nis.view())
    #print("NemoKerns found:")
    #for nk in nemokerns:
    #    print("nk",nk)
    #    print(" NK parent",nk._parent)
    #    print(" NK parent parent",nk._parent._parent)
    #    print(" NK parent parent parent",nk._parent._parent._parent)
    #    print("nk view", nk.view())
    assert False 
    return
    for invoke in psy.invokes.invoke_list:
        print(invoke.name)
        for loop in invoke.schedule.loops():
            kernels = loop.walk(NemoKern)
            if kernels and loop.loop_type == "levels":
                omp_trans.apply(loop)

    return psy
