import torch

if torch.cuda.is_available():
    torch.cuda.init()
