import os

import librosa
import numpy as np

SR = 8000
WINDOW_SIZE = 9984
N_MELS = 512
N_FFT = 1024
HOP_LENGTH = 256
DECIBEL_SCALE_FACTOR = 80
N_FRAMES = WINDOW_SIZE // HOP_LENGTH + 1
CLASS_NAMES = [
    "Aedes aegypti (macho)",
    "Aedes aegypti (femea)",
    "Outros mosquitos",
    "Ruido ambiental",
]

AQUI = os.path.dirname(os.path.abspath(__file__))
CAMINHO_PADRAO = os.path.join(AQUI, "modelos", "model_int8.tflite")

try:
    from ai_edge_litert.interpreter import Interpreter
except ImportError:
    try:
        from tflite_runtime.interpreter import Interpreter
    except ImportError as erro:
        raise ImportError(
            "Runtime TFLite nao encontrado. Instale ai-edge-litert "
            "ou tflite-runtime."
        ) from erro


def extrair_mel(audio):
    audio = np.asarray(audio, dtype=np.float32)
    mel = librosa.feature.melspectrogram(
        y=audio,
        sr=SR,
        n_mels=N_MELS,
        n_fft=N_FFT,
        hop_length=HOP_LENGTH,
    )
    mel = (librosa.power_to_db(mel, ref=np.max) / DECIBEL_SCALE_FACTOR) + 1.0
    mel = np.asarray(mel, dtype=np.float32)

    features = np.zeros((N_MELS + 1, N_FRAMES, 1), dtype=np.float32)
    frames = min(mel.shape[1], N_FRAMES)
    features[:N_MELS, :frames, 0] = mel[:, :frames]
    return features


def dividir_janelas(audio):
    audio = np.asarray(audio, dtype=np.float32).reshape(-1)
    if audio.size < WINDOW_SIZE:
        audio = np.pad(audio, (0, WINDOW_SIZE - audio.size))
    return [
        audio[inicio : inicio + WINDOW_SIZE]
        for inicio in range(0, audio.size - WINDOW_SIZE + 1, WINDOW_SIZE)
    ]


class InferenciaNumpy:
    def __init__(self, caminho_modelo=CAMINHO_PADRAO):
        self.interpreter = Interpreter(model_path=caminho_modelo)
        self.interpreter.allocate_tensors()

        self._input_details = self.interpreter.get_input_details()[0]
        self._output_details = self.interpreter.get_output_details()[0]

        self.input_shape = tuple(self._input_details["shape"])
        self.output_shape = tuple(self._output_details["shape"])
        self.input_index = self._input_details["index"]
        self.output_index = self._output_details["index"]

        self.input_scale, self.input_zero_point = self._input_details.get(
            "quantization", (0.0, 0)
        )
        self.output_scale, self.output_zero_point = self._output_details.get(
            "quantization", (0.0, 0)
        )

        self.input_dtype = self._input_details["dtype"]
        self.quantized_input = np.issubdtype(self.input_dtype, np.integer)
        self.quantized_output = np.issubdtype(self._output_details["dtype"], np.integer)
        self.num_classes = int(self.output_shape[-1])

        self.parametros = os.path.getsize(caminho_modelo)

    def _preparar_entrada(self, features):
        features = np.asarray(features, dtype=np.float32)
        if not self.quantized_input:
            return features.astype(self.input_dtype, copy=False)

        scale = self.input_scale if self.input_scale else 1.0
        quantized = np.round(features / scale).astype(np.int32) + self.input_zero_point
        return np.clip(quantized, -128, 127).astype(self.input_dtype)

    def _desquantizar_saida(self, saida):
        saida = np.asarray(saida, dtype=np.float32).reshape(-1, self.num_classes)
        if self.quantized_output and self.output_scale:
            saida = (saida - self.output_zero_point) * self.output_scale
        return saida

    def _probabilidades_medias(self, audio):
        probabilidades = []
        for janela in dividir_janelas(audio):
            features = extrair_mel(janela)[None, ...]
            self.interpreter.set_tensor(
                self.input_index, self._preparar_entrada(features)
            )
            self.interpreter.invoke()
            saida = self.interpreter.get_tensor(self.output_index)
            probabilidades.append(self._desquantizar_saida(saida)[0])
        return np.mean(probabilidades, axis=0)

    def prever(self, audio, n_samples=None, passo=None, semente=None):
        probabilidade_media = self._probabilidades_medias(audio)
        return {
            "p_mosquito": float(np.sum(probabilidade_media[:3])),
            "p_nao_mosquito": float(probabilidade_media[3]),
        }

    def prever_classes(self, audio):
        probabilidade_media = self._probabilidades_medias(audio)
        classe_prevista = int(np.argmax(probabilidade_media))
        return {
            "probabilidades": [float(p) for p in probabilidade_media],
            "classe_prevista": classe_prevista,
            "classe_nome": CLASS_NAMES[classe_prevista],
        }


def criar_inferencia(backend="numpy", **kwargs):
    return InferenciaNumpy(**kwargs)
