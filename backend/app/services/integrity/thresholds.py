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

# ---- confirmation over time (T7 / S6, S8): nothing fires on a single frame --------------------------
FACE_ABSENT_MIN_RUN_MS = 1000  # no face for this long (across windows too) is an absent face
MULTI_FACE_MIN_HEIGHT_FRAC = 0.08  # an extra face must be at least this tall (fraction of the frame height)
MULTI_FACE_MIN_YUNET_SCORE = 0.70  # YuNet confidence an extra face needs (the detector itself starts at 0.50)
MULTI_FACE_MIN_FRAMES = 2  # consecutive frames with an extra face, both detectors agreeing
MULTI_FACE_SINGLE_DETECTOR_MIN_WINDOWS = 2  # one detector alone must see it persist across this many windows
MULTI_FACE_TELEMETRY_MIN_MS = 500  # trusted browser telemetry with an extra face for this long also confirms
MULTI_FACE_TELEMETRY_GAP_MS = 250  # telemetry samples further apart than this are different stretches
IDENTITY_MIN_ELIGIBLE_FRAMES = 2  # frames with a verdict a window needs before it can be judged
IDENTITY_BAD_FRACTION = 0.6  # share of non-matching frames that makes a window a mismatch
IDENTITY_CONFIRM_WINDOWS = 2  # consecutive mismatching windows that make an incident
IDENTITY_STATELESS_MIN_FRAMES = 3  # without per-trial state one window must carry this many judged frames

# ---- gaze features (T6 / S5); the browser mirrors these in frontend/src/services/gaze-tracking.ts ------
GAZE_BLINK_SCORE = 0.55  # mean eyeBlinkLeft/Right at or above this is a blink
GAZE_CLOSED_LID_RATIO = 0.08  # without blendshapes: lid opening / eye width below this is a closed eye
GAZE_GAIN_H = 2.0  # iris offset from the corner midpoint, in half eye widths, scaled to roughly [-1, 1]
GAZE_GAIN_V = 1.5  # iris offset from the lid midpoint, in half lid openings
GAZE_BLENDSHAPE_WEIGHT = 0.5  # eyeLook* blendshapes vs iris geometry

# ---- calibrated screen zone (T6) ---------------------------------------------------------------
ZONE_HEAD_MARGIN_DEG = 5.0  # slack around the head pose reached at the five calibration targets
ZONE_GAZE_MARGIN = 0.15  # slack around the gaze reached at the five calibration targets
ZONE_MIN_HEAD_SPAN_DEG = 3.0  # an axis is distinguishable when the head moved at least this much...
ZONE_MIN_GAZE_SPAN = 0.10  # ...or the eyes moved at least this much between the targets
ZONE_MIN_USABLE_FRAMES = 2  # non-blink single-face frames needed per target

# Conservative absolute limits used while a trial has no calibrated zone.
DEFAULT_ZONE_PITCH_DEG = (-15.0, 20.0)
DEFAULT_ZONE_YAW_DEG = (-16.0, 16.0)
DEFAULT_ZONE_GAZE_H = (-0.6, 0.6)
DEFAULT_ZONE_GAZE_V = (-0.5, 0.6)

# ---- sustained gaze rule (T6 / S5) -------------------------------------------------------------
GAZE_TOLERANCE_MS = 1000  # a continuous stretch outside the screen zone shorter than this is tolerated
GAZE_BLINK_MAX_MS = 800  # eyes closed longer than this are not a blink: attention cannot be verified
GAZE_MAX_SAMPLE_SPAN_MS = 500  # the time a single sample stands for at most (sparse JPEG frames)
GAZE_RUN_GAP_MS = 1500  # away samples further apart than this are different runs
FRAME_TIME_MIN_TOLERANCE_MS = 150  # client frame timestamps may deviate this much (or half a slot) from even spacing

# ---- browser telemetry cross-check (T6 / S12) --------------------------------------------------
CLIENT_MATCH_MAX_DT_MS = 150  # a telemetry sample is comparable to a frame when it is this close in time
CLIENT_MISMATCH_HEAD_DEG = 12.0  # head pitch/yaw difference that counts as a disagreement
CLIENT_MISMATCH_GAZE = 0.4  # gaze_h/gaze_v difference that counts as a disagreement
CLIENT_MISMATCH_MIN_FRAMES = 2  # disagreeing frames that make the browser a mismatch
CLIENT_MIN_COMPARABLE = 2  # frames that must be comparable before the telemetry is trusted
TELEMETRY_MIN_SPACING_MS = 30  # telemetry faster than ~33 fps is not credible
TELEMETRY_MAX_SAMPLES = 60

# ---- face and mouth occlusion (T7 / S7) --------------------------------------------------------
# MediaPipe hallucinates landmarks on a covered face, so occlusion is judged on pixels (YCrCb chroma and edge energy
# of the eye, nose and mouth patches against the forehead/cheek skin of the same frame) relative to the trial's own
# reference, plus detector and identity evidence. A frame is occluded; an incident needs a continuous run.
OCC_MIN_RUN_MS = 1000  # a continuous stretch of occluded frames at least this long is an incident
OCC_REF_MIN_SAMPLES = 3  # clean frontal frames the trial's reference is built from before anything is judged
OCC_REF_ALPHA = 0.10  # how fast the reference follows lighting changes (only from frames with no anomaly)
OCC_REF_MIN_YUNET_SCORE = 0.80  # YuNet confidence a frame needs to feed the reference
OCC_MIN_EYE_DISTANCE_PX = 14.0  # smaller faces have patches too small to measure
OCC_PATCH_SIZE = (32, 16)  # every patch is resized to this (w, h) so edge energy does not depend on distance
OCC_EDGE_MIN_REF = 1.5  # a region whose reference edge energy is below this has no texture to lose
OCC_EDGE_COLLAPSE = 0.35  # edge energy at or below this share of the reference: the texture is gone...
OCC_EDGE_COLLAPSE_STRONG = 0.20  # ...and this low it is gone even if the colour looks the same (a hand)
OCC_CHROMA_DELTA = 12.0  # change of the region's chroma distance to the skin that goes with a lost texture
OCC_CHROMA_STRONG = 30.0  # a change this large is a cover by itself (mask, paper)
OCC_SKIN_SHIFT = 18.0  # the skin patches themselves moved this far in (Cr, Cb): the whole face is covered
OCC_YUNET_COLLAPSE_SCORE = 0.60  # MediaPipe sees a face but YuNet's confidence fell below this...
OCC_YUNET_COLLAPSE_DROP = 0.25  # ...and this far under the trial's usual YuNet confidence (or YuNet found nothing)
OCC_SIM_DROP = 0.20  # SFace similarity this far under the trial's matching level supports an occlusion

# ---- camera health (T7 / S8) -------------------------------------------------------------------
CAMERA_DARK_MEAN = 12.0  # mean gray level (0-255) below this is a covered or switched-off lens
CAMERA_UNIFORM_STD = 4.0  # gray standard deviation below this is a flat image (lens against a cloth, blank feed)
CAMERA_BLOCKED_MIN_MS = 1000  # dark or flat frames for at least this long are a blocked camera
CAMERA_FROZEN_MAX_DIFF = 0.30  # mean abs difference of consecutive thumbnails at or below this: the same image
CAMERA_FROZEN_MIN_MS = 1500  # the same image for at least this long is a frozen or looped camera
CAMERA_THUMB_SIZE = (64, 48)

# ---- voiceprint (T8 / S3, S11) -----------------------------------------------------------------
# Cosine similarity of 3D-Speaker ERes2Net embeddings. Tuned on synthetic signals only; T11 tunes them with
# real recordings, so treat every value below as a starting point.
VOICEPRINT_MIN_ENROLL_VOICED_S = 3.0  # voiced speech an enrollment needs; less is "insufficient", never a voiceprint
VOICEPRINT_MIN_VERIFY_VOICED_S = 1.0  # voiced speech a verification needs; less is "insufficient", never a verdict
VOICEPRINT_MAX_ENROLL_AUDIO_S = 12.0  # bound of the calibration recording (silence segment included)
VOICEPRINT_SEGMENT_S = 2.0  # enrollment embeds consecutive segments of this length and averages them
VOICEPRINT_MIN_SEGMENTS = 2  # segments an enrollment needs (so it can be checked for consistency)
VOICEPRINT_ENROLL_MIN_CONSISTENCY = 0.35  # lowest cosine between two enrollment segments; below: not one voice
VOICEPRINT_MATCH_THRESHOLD = 0.45  # similarity at or above this is the enrolled voice
VOICEPRINT_CLUSTER_MIN_VOICED_S = 1.0  # a diarized cluster needs this much speech to be compared with the voiceprint
VOICE_CONFIRM_EVALUATIONS = 2  # consecutive evaluations that make VOICE_MISMATCH / VOICE_UNVERIFIED
