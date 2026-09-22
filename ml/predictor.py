import json
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
import tensorflow as tf

MODEL_PATH = "ml/genre_model.keras"
LABELS_PATH = "ml/labels.json"
CONFIG_PATH = "ml/feature_config.json"

model = tf.keras.models.load_model(MODEL_PATH)

with open(LABELS_PATH, "r") as f:
    labels = json.load(f)["classes"]

with open(CONFIG_PATH, "r") as f:
    config = json.load(f)

SAMPLE_RATE = config["sample_rate"]
SEGMENT_SAMPLES = config["segment_samples"]
N_MFCC = config["n_mfcc"]
N_MELS = config["n_mels"]
N_FFT = config["n_fft"]
HOP_LENGTH = config["hop_length"]

NORMALIZATION_MEAN = np.float32(
    config["normalization_mean"][0]
)

NORMALIZATION_STD = np.float32(
    config["normalization_std"][0]
)


def load_audio(file_path):
    audio, sample_rate = sf.read(file_path)

    if audio.ndim > 1:
        audio = np.mean(audio, axis=1)

    audio = audio.astype(np.float32)

    if sample_rate != SAMPLE_RATE:
        audio = resample_poly(
            audio,
            SAMPLE_RATE,
            sample_rate
        ).astype(np.float32)

    return audio


def split_audio(audio):
    segments = []

    for start in range(0, len(audio), SEGMENT_SAMPLES):
        segment = audio[
            start:start + SEGMENT_SAMPLES
        ]

        if len(segment) < SEGMENT_SAMPLES:
            segment = np.pad(
                segment,
                (0, SEGMENT_SAMPLES - len(segment))
            )

        segments.append(segment)

    return segments


def hz_to_mel(frequency):
    return 2595.0 * np.log10(
        1.0 + frequency / 700.0
    )


def mel_to_hz(mel):
    return 700.0 * (
        10.0 ** (mel / 2595.0) - 1.0
    )


def create_mel_filterbank():
    mel_min = hz_to_mel(0)
    mel_max = hz_to_mel(SAMPLE_RATE / 2)

    mel_points = np.linspace(
        mel_min,
        mel_max,
        N_MELS + 2
    )

    hz_points = mel_to_hz(mel_points)

    bins = np.floor(
        (N_FFT + 1) * hz_points / SAMPLE_RATE
    ).astype(int)

    filterbank = np.zeros(
        (N_MELS, N_FFT // 2 + 1),
        dtype=np.float32
    )

    for i in range(N_MELS):
        left = bins[i]
        center = bins[i + 1]
        right = bins[i + 2]

        if center > left:
            filterbank[i, left:center] = (
                np.arange(left, center) - left
            ) / (center - left)

        if right > center:
            filterbank[i, center:right] = (
                right - np.arange(center, right)
            ) / (right - center)

    return filterbank


def compute_spectrogram(audio):
    window = np.hanning(N_FFT)

    padded_audio = np.pad(
        audio,
        (N_FFT // 2, N_FFT // 2),
        mode="constant"
    )

    frames = []

    for start in range(
        0,
        len(padded_audio) - N_FFT + 1,
        HOP_LENGTH
    ):
        frame = padded_audio[
            start:start + N_FFT
        ]

        frame = frame * window

        spectrum = np.abs(
            np.fft.rfft(frame)
        ) ** 2

        frames.append(spectrum)

    return np.array(frames).T


def dct_type_ii(matrix, number_of_coefficients):
    number_of_mel_bins = matrix.shape[0]

    n = np.arange(number_of_mel_bins)
    k = np.arange(number_of_coefficients)

    basis = np.cos(
        np.pi / number_of_mel_bins
        * (n[:, None] + 0.5)
        * k[None, :]
    )

    basis[0, :] *= 1.0 / np.sqrt(2.0)

    return np.sqrt(
        2.0 / number_of_mel_bins
    ) * np.dot(
        basis.T,
        matrix
    )


def extract_features(audio):
    spectrogram = compute_spectrogram(audio)

    filterbank = create_mel_filterbank()

    mel_spectrogram = np.dot(
        filterbank,
        spectrogram
    )

    mel_spectrogram = np.maximum(
        mel_spectrogram,
        1e-10
    )

    mel_db = 10.0 * np.log10(
        mel_spectrogram
    )

    mfcc = dct_type_ii(
        mel_db,
        N_MFCC
    )

    features = np.concatenate(
        [mfcc, mel_db],
        axis=0
    )

    if features.shape[1] < 130:
        features = np.pad(
            features,
            (
                (0, 0),
                (0, 130 - features.shape[1])
            )
        )
    else:
        features = features[:, :130]

    features = (
        features - NORMALIZATION_MEAN
    ) / NORMALIZATION_STD

    return features.astype(np.float32)


def prepare_segment(segment):
    features = extract_features(segment)

    return features[
        np.newaxis,
        ...,
        np.newaxis
    ]


def predict_file(file_path):
    audio = load_audio(file_path)
    segments = split_audio(audio)

    inputs = np.concatenate(
        [prepare_segment(segment) for segment in segments],
        axis=0
    )

    probabilities = model.predict(
        inputs,
        verbose=0
    )

    predicted_indices = np.argmax(
        probabilities,
        axis=1
    )

    confidences = np.max(
        probabilities,
        axis=1
    )

    vote_counts = np.bincount(
        predicted_indices,
        minlength=len(labels)
    )

    winning_votes = int(
        np.max(vote_counts)
    )

    winning_indices = np.where(
        vote_counts == winning_votes
    )[0]

    if len(winning_indices) == 1:
        winning_index = int(
            winning_indices[0]
        )
    else:
        confidence_totals = {
            index: float(
                np.sum(
                    confidences[
                        predicted_indices == index
                    ]
                )
            )
            for index in winning_indices
        }

        winning_index = max(
            confidence_totals,
            key=confidence_totals.get
        )

    predicted_genre = labels[winning_index]

    return {
        "genre": predicted_genre,
        "winning_votes": winning_votes,
        "total_segments": len(segments)
    }



    