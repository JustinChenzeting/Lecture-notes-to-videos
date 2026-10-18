#!/usr/bin/env python3
"""Voice-clone TTS worker (Chatterbox), run in its own venv made by `lv.py setup --clone`.

Backends: Apple MLX (mlx-audio, Apple silicon) or the PyTorch `chatterbox-tts` package
(CUDA, Apple MPS or CPU) everywhere else; whichever is installed is used.

render_lecture.py calls it with a JSON job file:
  {"reference": "...wav", "exaggeration": 0.4, "cfg_weight": 0.5,
   "jobs": [{"text": "...", "out": "...wav"}, ...]}
`--preload` only loads (and on first use downloads) the model.
Each line is split into sentences (Chatterbox drifts on long inputs), and every
sentence is checked against its expected length: autoregressive TTS sometimes
rambles or stops early, so out-of-range takes are regenerated with a new seed.
Output: mono WAV at the model's rate, written to <out>.part.wav then renamed.

MLX instead of PyTorch on Apple silicon: the PyTorch/MPS build slowed to 5-7x real time
within long sentences; mlx-community/Chatterbox-TTS-fp16 runs at about real time with
equal or better speaker similarity (tested Oct 2026).
"""
import json, os, re, sys, zlib

import numpy as np
import soundfile as sf

MLX_MODEL = "mlx-community/Chatterbox-TTS-fp16"
GAP = 0.18  # seconds between sentences of one line


class MLX:
    def __init__(self):
        import mlx.core as mx
        from mlx_audio.tts.utils import load_model
        self.mx, self.m = mx, load_model(MLX_MODEL)
        self.sr = self.m.sample_rate

    def prepare(self, ref_path, exa):
        ref, sr = sf.read(ref_path, dtype="float32")
        if ref.ndim > 1:
            ref = ref.mean(axis=1)
        if sr != self.sr:
            sys.exit(f"reference must be {self.sr} Hz mono, got {sr}")
        self.conds = self.m.prepare_conditionals(self.mx.array(ref), sr, exa)

    def say(self, s, seed, exa, cfgw):
        self.mx.random.seed(seed)
        return np.concatenate([np.array(r.audio, dtype=np.float32).reshape(-1) for r in
                               self.m.generate(s, conds=self.conds, exaggeration=exa, cfg_weight=cfgw, verbose=False)])


class Torch:
    def __init__(self):
        import torch
        from chatterbox.tts import ChatterboxTTS
        dev = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
        self.torch, self.m = torch, ChatterboxTTS.from_pretrained(device=dev)
        self.sr = self.m.sr

    def prepare(self, ref_path, exa):
        self.m.prepare_conditionals(ref_path, exaggeration=exa)

    def say(self, s, seed, exa, cfgw):
        self.torch.manual_seed(seed)
        return self.m.generate(s, exaggeration=exa, cfg_weight=cfgw).squeeze().cpu().numpy().astype(np.float32)


def backend():
    try:
        import mlx_audio  # noqa: F401
        return MLX()
    except ImportError:
        return Torch()


def sentences(text):
    out = []
    for p in re.split(r"(?<=[.!?])\s+", text.strip()):
        if out and len(p.split()) < 4:  # fold tiny fragments into the previous sentence
            out[-1] += " " + p
        else:
            out.append(p)
    return out


def main():
    if sys.argv[1:] == ["--preload"]:
        backend()
        print("chatterbox model ready")
        return
    cfg = json.load(open(sys.argv[1]))
    exa, cfgw = cfg.get("exaggeration", 0.5), cfg.get("cfg_weight", 0.5)
    m = backend()
    m.prepare(cfg["reference"], exa)
    for n, job in enumerate(cfg["jobs"], 1):
        chunks = []
        for s in sentences(job["text"]):
            words = len(s.split())
            lo, hi = 0.18 * words, 0.55 * words + 1.5  # seconds; normal speech ~0.33 s/word
            for attempt in range(4):
                w = m.say(s, zlib.crc32(s.encode()) + attempt, exa, cfgw)  # reproducible per sentence
                d = len(w) / m.sr
                if lo <= d <= hi:
                    break
                print(f"  retry {attempt + 1}: {d:.1f}s for {words} words: {s[:50]}", file=sys.stderr)
            else:
                sys.exit(f"chatterbox could not produce a sane take for: {s}")
            chunks += [w, np.zeros(int(GAP * m.sr), dtype=np.float32)]
        audio = np.concatenate(chunks[:-1])
        part = job["out"][:-4] + ".part.wav"
        sf.write(part, audio, m.sr, subtype="PCM_16")
        os.replace(part, job["out"])
        print(f"  [{n}/{len(cfg['jobs'])}] {len(audio) / m.sr:.1f}s", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
