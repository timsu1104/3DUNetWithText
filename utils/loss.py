import torch
import torch.nn.functional as F
from utils.registry import LOSS_REGISTRY

@LOSS_REGISTRY.register()
def TextContrastive(pc: torch.Tensor, text: torch.Tensor, has_text):
    """
    pc: B, m
    text: B', num_text, m
    """
    if has_text.size(0) == 0:
        return 0
    assert text.ndim == 3, text.size()
    similarity = text @ pc.T # B', num_text, B
    num_text = similarity.size(1)
    labels = torch.tile(has_text[:, None], (1, num_text))
    contrast_loss = F.cross_entropy(similarity.transpose(1, 2), labels)
    return contrast_loss

@LOSS_REGISTRY.register()
def Classification(logits: torch.Tensor, labels: torch.Tensor):
    """
    Loss for scene level classification and point level classification.
    scene level: logits (B, C), labels (B, C)
    scene level: logits (N, C), labels (N, )
    """
    if labels.ndim == 2:
        return F.multilabel_soft_margin_loss(logits, labels)
    elif labels.ndim == 1:
        mask = labels != -100
        logits_for_loss = logits[mask]
        labels_for_loss = labels[mask]
        return F.cross_entropy(logits_for_loss, labels_for_loss)