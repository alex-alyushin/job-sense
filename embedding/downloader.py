from pathlib import Path
from huggingface_hub import hf_hub_download

MODEL_REPO = "Xenova/all-MiniLM-L6-v2"
MODEL_DIR = Path(__file__).parent / "models" / "all-MiniLM-L6-v2"

def ensure_model() -> Path:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    tokenizer_path = MODEL_DIR / "tokenizer.json"
    model_path = MODEL_DIR / "model.onnx"

    if not tokenizer_path.exists():
        hf_hub_download(
            repo_id=MODEL_REPO,
            filename="tokenizer.json",
            local_dir=MODEL_DIR,
        )

    if not model_path.exists():
        hf_hub_download(
            repo_id=MODEL_REPO,
            filename="onnx/model.onnx",
            local_dir=MODEL_DIR,
        )

        downloaded_model = MODEL_DIR / "onnx/model.onnx"
        downloaded_model.rename(model_path)

    return MODEL_DIR
