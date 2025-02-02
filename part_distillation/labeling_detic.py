# Copyright (c) Meta Platforms, Inc. and affiliates.

# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.


import copy
import logging
import numpy as np
import torch
import torch.nn.functional as F 
import sys 
import os 

from typing import Dict, List, Optional, Tuple
from detectron2.data import transforms as T
from detectron2.structures import Boxes, Instances
from detectron2.modeling.meta_arch.build import META_ARCH_REGISTRY
from Detic.detic.modeling.meta_arch.custom_rcnn import CustomRCNN 
from .utils.utils import proposals_to_coco_json
from detectron2.data import detection_utils as utils



@META_ARCH_REGISTRY.register()
class LabelingDetic(CustomRCNN):
    def inference(
        self,
        batched_inputs: Tuple[Dict[str, torch.Tensor]],
        detected_instances: Optional[List[Instances]] = None,
        do_postprocess: bool = True, 
    ):
        assert not self.training
        assert detected_instances is None

        images = self.preprocess_image(batched_inputs)
        features = self.backbone(images.tensor)
        proposals, _ = self.proposal_generator(images, features, None)

        class_ids = None
        if self.labeling_mode == 'max-gt-label':
            class_ids = images.tensor.new_tensor([self.metadata.class_code_to_class_id[input_per_image["class_code"]] \
                            for input_per_image in batched_inputs]).long()
        results, _ = self.roi_heads(images, features, proposals, class_ids=class_ids)
        if do_postprocess:
            assert not torch.jit.is_scripting(), \
                "Scripting is not supported for postprocess."
            results = CustomRCNN._postprocess(
                results, batched_inputs, images.image_sizes)
        
        output_list = self.save_detic_prediction(batched_inputs, results)

        return output_list


    def register_metadata(self, metadata, labeling_mode, score_thres, debug):
        self.metadata = metadata
        self.root_save_path = metadata.save_path 
        self.labeling_mode = labeling_mode 
        self.score_thres = score_thres
        self.debug = debug



    def save_detic_prediction(self, batched_inputs, results):
        """
        results: list[Dict(Instances)]. 

        each result has:
           -  result.pred_boxes
           -  result.scores 
           -  result.pred_classes
           -  result.pred_masks 
        """
        output_list = []
        for input_per_image, instance_dict in zip(batched_inputs, results):
            gt_class = self.metadata.class_code_to_class_id[input_per_image["class_code"]]
            pred_classes = instance_dict["instances"].pred_classes.cpu()
            # print(pred_classes, gt_class, input_per_image["class_code"],  flush=True)
            idxs = pred_classes == gt_class

            if idxs.any() and self.labeling_mode == 'max-gt-label':
                masks = instance_dict["instances"].pred_masks.cpu()[idxs]
                scores = instance_dict["instances"].scores.cpu()[idxs]
                boxes = instance_dict["instances"].pred_boxes.tensor.cpu()[idxs]

                topk_idxs = scores.topk(min(10, len(scores)))[1].flatten()

                masks_selected = masks[topk_idxs]
                scores_selected = scores[topk_idxs]
                boxes_selected = boxes[topk_idxs]
                pred_classes = pred_classes[idxs][topk_idxs]
                pred_names = [self.metadata.class_names[i] for i in pred_classes]
            else:
                # no output with gt-label or "max-score" mode
                masks = instance_dict["instances"].pred_masks.cpu()
                scores = instance_dict["instances"].scores.cpu()
                boxes = instance_dict["instances"].pred_boxes.tensor.cpu()

                topk_idxs = scores.topk(min(10, len(scores)))[1].flatten()

                masks_selected = masks[topk_idxs]
                scores_selected = scores[topk_idxs]
                boxes_selected = boxes[topk_idxs]
                pred_classes = pred_classes[topk_idxs]
                pred_names = [self.metadata.class_names[i] for i in pred_classes]

                if self.labeling_mode == 'human-only':
                    assert max(pred_classes) < 5, '[human-only] mode only considers ["person", "man", "woman", "toddler", "human"]'

            filtered_idxs = scores_selected > self.score_thres

            res = None
            if filtered_idxs.any():
                masks_selected = masks_selected[filtered_idxs]
                scores_selected = scores_selected[filtered_idxs]
                boxes_selected = boxes_selected[filtered_idxs]
                pred_classes = pred_classes[filtered_idxs]
                pred_names = [pred_names[i] for i in filtered_idxs] # list of str

                H, W = masks_selected.shape[-2:]
                res = {"file_name": input_per_image["file_name"],
                        "file_path": input_per_image["file_path"],
                        "class_code": input_per_image["class_code"],
                        "class_name": input_per_image["class_name"],
                        "object_masks": proposals_to_coco_json(masks_selected) \
                                        if not self.debug else masks_selected,
                        "object_boxes": boxes_selected,
                        "object_scores": scores_selected,
                        "height": H, 
                        "width": W, 
                        "pred_names": pred_names,
                        }
            
            if not self.debug and res is not None:
                torch.save(res, os.path.join(self.root_save_path, 
                                            input_per_image["class_code"], 
                                            input_per_image["file_name"]))
                    
            output_list.append(res)
            
        return output_list 



