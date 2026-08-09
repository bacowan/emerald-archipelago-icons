import torch
import open_clip

def setup():
    # use GPU if available, CPU otherwise
    device = "cuda" if torch.cuda.is_available() else "cpu"

    # load the model and preprocessor
    model, _, preprocess = open_clip.create_model_and_transforms(
        "ViT-B-32",
        # a good size/accuracy tradeoff; bigger models exist (ViT-L-14) if you want more accuracy at the cost of speed/size
        pretrained="laion2b_s34b_b79k",  # which trained checkpoint to use for that architecture
    )

    # use inference mode instead of training mode
    model = model.to(device).eval()

    return model, preprocess, device