!-------------------------------------------------------------------------------
! BSD 3-Clause License
!
! Copyright (c) 2017-2024, Science and Technology Facilities Council
! All rights reserved.
!
! Redistribution and use in source and binary forms, with or without
! modification, are permitted provided that the following conditions are met:
!
! * Redistributions of source code must retain the above copyright notice, this
!   list of conditions and the following disclaimer.
!
! * Redistributions in binary form must reproduce the above copyright notice,
!   this list of conditions and the following disclaimer in the documentation
!   and/or other materials provided with the distribution.
!
! * Neither the name of the copyright holder nor the names of its
!   contributors may be used to endorse or promote products derived from
!   this software without specific prior written permission.
!
! THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
! AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
! IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
! DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
! FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
! DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
! SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
! CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
! OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
! OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
! -----------------------------------------------------------------------------
! Authors: R. W. Ford and A. R. Porter, STFC Daresbury Lab
! Modified: I. Kavcic, Met Office

program operator_example

  use constants_mod,                 only : i_def
  use fs_continuity_mod,             only : W2, W3
  use function_space_collection_mod, only : function_space_collection
  use field_mod,                     only : field_type
  use operator_mod,                  only : operator_type
  use quadrature_xyoz_mod,           only : quadrature_xyoz_type
  use assemble_weak_derivative_w3_w2_kernel_mod, &
                                     only : assemble_weak_derivative_w3_w2_kernel_type

  implicit none

  type(field_type)                    :: coord(3)
  type(operator_type)                 :: mapping
  type(quadrature_xyoz_type), pointer :: qr => null
  integer(i_def)                      :: mesh_id = 1
  integer(i_def)                      :: element_order = 0

  mapping = operator_type(function_space_collection%get_fs(mesh_id,element_order,W3), &
                          function_space_collection%get_fs(mesh_id,element_order,W2))

  call invoke(assemble_weak_derivative_w3_w2_kernel_type(mapping, coord, qr))

end program operator_example
