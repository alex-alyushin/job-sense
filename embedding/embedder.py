import numpy as np
import onnxruntime as ort

from tokenizers import Tokenizer

from embedding.downloader import ensure_model


class Embedder:

    def __init__(self):
        model_dir = ensure_model()

        self.tokenizer = Tokenizer.from_file(
            str(model_dir / "tokenizer.json")
        )

        self.session = ort.InferenceSession(
            str(model_dir / "model.onnx"),
            providers=["CPUExecutionProvider"],
        )

        self.input_names = {
            inp.name
            for inp in self.session.get_inputs()
        }

        self.tokenizer.enable_padding()
        # 512 is limit for all-MiniLM-L6-v2 (BERT)
        self.tokenizer.enable_truncation(max_length=256)


    def encode(self, text: str, normalize: bool = True) -> np.ndarray:
        return self.encode_batch([text], normalize=normalize)[0]


    def encode_batch(self, texts: list[str], normalize: bool = True) -> np.ndarray:

        encoded = self.tokenizer.encode_batch(texts)

        feed = {}

        if "input_ids" in self.input_names:
            feed["input_ids"] = np.array(
                [e.ids for e in encoded],
                dtype=np.int64,
            )

        if "attention_mask" in self.input_names:
            feed["attention_mask"] = np.array(
                [e.attention_mask for e in encoded],
                dtype=np.int64,
            )

        if "token_type_ids" in self.input_names:
            feed["token_type_ids"] = np.array(
                [e.type_ids for e in encoded],
                dtype=np.int64,
            )

        hidden = self.session.run(None, feed)[0]

        mask = feed["attention_mask"][..., None]

        pooled = (
            (hidden * mask).sum(axis=1)
            / mask.sum(axis=1)
        )

        if normalize:
            pooled = pooled / np.linalg.norm(
                pooled,
                axis=1,
                keepdims=True,
            )

        return pooled
