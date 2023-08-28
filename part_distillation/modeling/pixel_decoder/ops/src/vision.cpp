/*!
------------------------------------------------------------------------------------------------
Deformable DETR
Copyright (c) 2020 SenseTime. All Rights Reserved.
Licensed under the Apache License, Version 2.0 [see LICENSE for details]
------------------------------------------------------------------------------------------------
Modified from https://github.com/chengdazhi/Deformable-Convolution-V2-PyTorch/tree/pytorch_1.0.0
------------------------------------------------------------------------------------------------

Copyright (c) Meta Platforms, Inc. and affiliates.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
Modified from https://github.com/fundamentalvision/Deformable-DETR
*/

#include "ms_deform_attn.h"

PYBIND11_MODULE(TORCH_EXTENSION_NAME, m) {
  m.def("ms_deform_attn_forward", &ms_deform_attn_forward, "ms_deform_attn_forward");
  m.def("ms_deform_attn_backward", &ms_deform_attn_backward, "ms_deform_attn_backward");
}