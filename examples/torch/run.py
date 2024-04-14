import sys
import time

print("Arguments:", sys.argv)
start = time.time()

import torch

torch.tensor(1, device="cuda")

end = time.time()
print("Elapsed:", end - start)
