"""Every tunable threshold of the integrity engine, in one place (T11 tunes them with real recordings).

Values are exactly the ones the supervision service used before the extraction; changing one here changes
behavior everywhere the engine is used.
"""
from app.services.biometric_service import SFACE_COSINE_THRESHOLD

# ---- frame decoding (decompression-bomb guard) -------------------------------------------------
MAX_FRAME_WIDTH = 1920
MAX_FRAME_HEIGHT = 1080

# ---- identity ----------------------------------------------------------------------------------
IDENTITY_COSINE_THRESHOLD = SFACE_COSINE_THRESHOLD
REFERENCE_EMBEDDING_DIM = 128

# ---- model loading -----------------------------------------------------------------------------
MP_RETRY_COOLDOWN_S = 30.0  # a failed MediaPipe init is retried after this long
MP_NUM_FACES = 3
MP_MIN_FACE_CONFIDENCE = 0.45
YUNET_INPUT_SIZE = (320, 240)
YUNET_SCORE_THRESHOLD = 0.50
YUNET_NMS_THRESHOLD = 0.3
YUNET_TOP_K = 5

# ---- MediaPipe head pose (degrees) -------------------------------------------------------------
MP_MATRIX_WEIGHT = 0.55  # facial transformation matrix vs landmark geometry
MP_LANDMARK_WEIGHT = 0.45
MP_EXTREME_DOWN_PITCH_DEG = 21.0
MP_DOWN_PITCH_WITH_EYES_DEG = 15.0
MP_DOWN_EYE_LOOK = 0.42
MP_FRONTAL_MAX_YAW_DEG = 13.0
MP_SIDE_YAW_DEG = 15.5
MP_SIDE_DELTA_YAW_DEG = 13.5
MP_DOWN_DELTA_PITCH_DEG = 9.5
MP_DOWN_DELTA_PITCH_SOFT_DEG = 6.5
MP_DOWN_DELTA_EYE_SOFT = 0.14
MP_DOWN_REL_DROP_SOFT = 0.15
MP_DOWN_DELTA_EYE_STRONG = 0.25
MP_DOWN_DELTA_PITCH_WITH_EYES_DEG = 4.0
MP_DOWN_REL_DROP_STRONG = 0.20
MP_DOWN_DELTA_PITCH_WITH_DROP_DEG = 5.0

# ---- YuNet fallback head pose (ratios) ---------------------------------------------------------
YN_EXTREME_DOWN_PITCH_RATIO = 0.68
YN_EXTREME_DOWN_NOSE_MOUTH = 0.23
YN_DOWN_PITCH_RATIO = 0.65
YN_DOWN_NOSE_MOUTH = 0.27
YN_FRONTAL_MAX_YAW_RATIO = 0.13
YN_SIDE_YAW_RATIO = 0.135
YN_SIDE_DELTA_YAW_RATIO = 0.12
YN_PITCH_BASE = 0.53
YN_PITCH_DEG_SCALE = 75.0
YN_YAW_DEG_SCALE = 90.0
YN_DOWN_DELTA_PITCH = 0.045
YN_DOWN_REL_DROP_NM = 0.15
YN_DOWN_DELTA_NOSE_BOX = 0.030
YN_DOWN_REL_DROP_NM_STRONG = 0.18
YN_DOWN_REL_DROP_E2M = 0.09
YN_DOWN_DELTA_NOSE_BOX_SOFT = 0.028
YN_DOWN_DELTA_EYE_BOX_SOFT = 0.026
YN_DOWN_REL_DROP_E2M_STRONG = 0.13
YN_DOWN_DELTA_EYE_BOX = 0.028
YN_DOWN_DELTA_FACE_Y = 0.035
YN_DOWN_DELTA_PITCH_STRONG = 0.070
YN_DOWN_REL_DROP_NM_EXTREME = 0.26

# ---- per-session baseline ----------------------------------------------------------------------
MAX_TRACKED_SESSIONS = 256
BASELINE_WARMUP_SAMPLES = 4.0
BASELINE_ADAPT_ALPHA = 0.12
BASELINE_PITCH_TOLERANCE_DEG = 2.5
BASELINE_NOSE_MOUTH_TOLERANCE = 0.015

# ---- audio -------------------------------------------------------------------------------------
AUDIO_SAMPLE_RATE = 16_000
AUDIO_LENGTH_TOLERANCE = 0.25  # accepted deviation from duration_ms * 16 kHz
AUDIO_MIN_SAMPLES = 160
VAD_CHUNK_SAMPLES = 480  # 30 ms at 16 kHz
VAD_AGGRESSIVENESS = 3  # strictest WebRTC mode, same as CalibrationAudioService
SILENCE_RMS_FLOOR = 0.005  # below this nothing is fed to the VAD
VAD_MIN_VOICED_CHUNKS = 6  # 180 ms
VAD_MIN_CONTIGUOUS_CHUNKS = 3  # 90 ms
HIGH_NOISE_RMS = 0.22
HIGH_NOISE_NON_SPEECH_RMS = 0.14

# ---- diarization (multiple speakers) -----------------------------------------------------------
DIARIZATION_BUFFER_SAMPLES = 38_400  # 2.4 s of voiced audio carried to the next window
DIARIZATION_REMEMBER_MIN_VOICED_CHUNKS = 6
DIARIZATION_MIN_SAMPLES = 24_000  # 1.5 s
DIARIZATION_MIN_VOICED_CHUNKS = 8
SPEAKER_MIN_DURATION_S = 0.25
SPEAKER_OVERLAP_MIN_S = 0.12

# ---- mouth movement ----------------------------------------------------------------------------
MOUTH_OPEN_FRAME_SCORE = 0.035
MOUTH_MIN_PEAK_SCORE = 0.038
MOUTH_MIN_DYNAMIC_RANGE = 0.014
MOUTH_MIN_OPEN_FRAMES = 2
MOUTH_PATCH_ACTIVE_STEP = 0.011
MOUTH_PATCH_PEAK = 0.014
MOUTH_PATCH_MEAN = 0.0075
MOUTH_PATCH_MIN_ACTIVE_STEPS = 2

# ---- window aggregation ------------------------------------------------------------------------
FACE_ABSENT_MIN_EMPTY_FRAMES = 2  # also needs more than half of the frames to be empty
