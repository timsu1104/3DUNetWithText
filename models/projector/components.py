import torch
from torch import nn
import sparseconvnet as scn

def cropBox(coords: torch.Tensor, feats: torch.Tensor, boxes: torch.Tensor, transform: tuple):
    """
    coords: (N, 3+1), 1 for batch
    feats: (N, C)
    box: (M, 6+1), 1 for batch
    transform:
        axis_align_matrix: (B, 4, 4)
        -center, @rot.inv, +offset
    
    Return
    --------
    cropped cloud, (N', 3+1), (N', C)
    """
    coords_pool = []
    feats_pool = []
    axis_align_matrix, centers, rots, offsets = transform
    for id, box in enumerate(boxes):
        center = box[:3]
        length = box[3:6]
        mincoords = center - length / 2
        maxcoords = center + length / 2
        batch_id = box[-1]
        
        batch_mask = (coords[:, -1] == batch_id)
        batch_pc = coords[batch_mask, :3]
        batch_pc = ((batch_pc \
                     - offsets[batch_id.long()]) \
                    @ rots[batch_id.long()] \
                    + centers[batch_id.long()])
        batch_pc = torch.cat([batch_pc, torch.ones((batch_pc.size(0), 1), device=coords.device)], -1)
        batch_pc = batch_pc @ axis_align_matrix[batch_id.long()].T
        
        batch_feats = feats[batch_mask]
        selected_mask = torch.prod(batch_pc[:, :3] >= mincoords, -1) * torch.prod(batch_pc[:, :3] <= maxcoords, -1)
        
        cropped_feats = batch_feats[selected_mask]
        cropped_coords = batch_pc[selected_mask]
        
        # centering
        cropped_coords[:, :3] -= cropped_coords[:, :3].min(0)[0]
        cropped_coords[:, :3] /= (cropped_coords[:, :3].max(0)[0] - cropped_coords[:, :3].min(0)[0])
        cropped_coords[:, -1] = id
        
        coords_pool.append(cropped_coords)
        feats_pool.append(cropped_feats)
    new_coords = torch.cat(coords_pool)
    new_feats = torch.cat(feats_pool)
    return new_coords, new_feats

class MattingModule(nn.Module):
    """
    Matting the pointcloud
    """
    def __init__(self, in_channels, out_channels=2) -> None:
        super().__init__()
        self.model = nn.Linear(in_channels, out_channels)
    
    def forward(self, coords: torch.Tensor, feats: torch.Tensor):
        return coords, self.model(feats)

class Voxelizer(nn.Module):
    """
    Parameters
    -------
    coords, feats
    
    Return
    -------
    view_mask: (B', C, H, W)
    """
    def __init__(self, channels, resolution=256) -> None:
        super().__init__()
        self.res = resolution
        self.voxelizer = scn.Sequential(
            scn.InputLayer(3, resolution, mode=4),
            scn.SparseToDense(3, channels)
        )
    # maxpooling
    def forward(self, coords: torch.Tensor, feats: torch.Tensor, view='HWZ'):
        coords[:, :-1] = coords[:, :-1] * self.res
        print("Start voxelize")
        voxel = self.voxelizer([coords, feats]) # [B, C, H, W, Z]
        
        _, _, H, W, Z = voxel.size()
        print(voxel.size())
        assert H == W == Z == self.res
        assert len(view) > 0, "view not selected!"
        
        view_mask = []
        if 'H' in view:
            view_mask.append(torch.max(voxel, dim=-3)[0])
        if 'W' in view:
            view_mask.append(torch.max(voxel, dim=-2)[0])
        if 'Z' in view:
            view_mask.append(torch.max(voxel, dim=-1)[0])
        view_mask = torch.cat(view_mask) if len(view_mask) > 0 else view_mask[0]
        return view_mask
    
if __name__ == '__main__':
    import numpy as np
    box = np.load('/home/zhengyuan/code/3D_weakly_segmentation_backbone/3DUNetWithText/ops/GeometricSelectiveSearch/gss/computed_proposal_scannet/fv_inst100_p100_d300/scene0015_00_prop.npy')
    print(box.shape)
    print(box[:5])