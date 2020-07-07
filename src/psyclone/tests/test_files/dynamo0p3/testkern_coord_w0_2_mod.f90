! -----------------------------------------------------------------------------
! BSD 3-Clause License
!
! Copyright (c) 2017-2020, Science and Technology Facilities Council
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
! THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
! "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
! LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
! FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
! COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
! INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
! BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
! LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
! CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
! LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
! ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
! POSSIBILITY OF SUCH DAMAGE.
!-------------------------------------------------------------------------------
! Authors R. W. Ford STFC Daresbury Lab, C. M. Maynard Met Office/University of Reading
! Modified I. Kavcic Met Office

module testkern_coord_w0_2_mod

  use argument_mod
  use fs_continuity_mod
  use kernel_mod
  use constants_mod

  implicit none
  
  type, extends(kernel_type) :: testkern_coord_w0_2_type
     type(arg_type), dimension(2) :: meta_args = &
          (/ arg_type(gh_field*3, gh_inc, w0),   &
             arg_type(gh_field,   gh_inc, w0)    &
          /)
     integer :: iterates_over = cells
   contains
     procedure, nopass :: code => testkern_coord_w0_2_code
  end type testkern_coord_w0_2_type

contains

  subroutine testkern_coord_w0_2_code(nlayers, field1_v1, &
                                      field1_v2, field1_v3, &
                                      field2, ndf_w0, undf_w0, map_w0)

    implicit none

    integer(kind=i_def), intent(in) :: nlayers
    integer(kind=i_def), intent(in) :: ndf_w0
    integer(kind=i_def), intent(in) :: undf_w0
    integer(kind=i_def), intent(in), dimension(ndf_w0) :: map_w0
    real(kind=r_def), intent(inout), dimension(undf_w0) :: field1_v1
    real(kind=r_def), intent(inout), dimension(undf_w0) :: field1_v2
    real(kind=r_def), intent(inout), dimension(undf_w0) :: field1_v3
    real(kind=r_def), intent(inout), dimension(undf_w0) :: field2

  end subroutine testkern_coord_w0_2_code

end module testkern_coord_w0_2_mod