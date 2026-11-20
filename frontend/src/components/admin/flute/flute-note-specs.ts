export type FluteNoteName =
  | "SI"
  | "LA"
  | "SOL"
  | "DO6"
  | "RE6"
  | "FA#"
  | "FA"
  | "MI"
  | "RE"
  | "DO"
  | "MI6"

export type FluteVariationType =
  | "sostenida"
  | "rapida"
  | "angulo_suave"

export interface FluteNoteSpec {
  note: FluteNoteName
  displayName: string
  handsRequired: 1 | 2
  /** Back thumb hole state */
  thumbState: "tapado" | "abierto" | "medio"
  /** 7 front holes from top (1-3 Left Hand, 4-7 Right Hand) */
  frontHoles: [boolean, boolean, boolean, boolean, boolean, boolean, boolean]
  handTip: string
  difficultyLevel: 1 | 3
}

export const FLUTE_AUDIO_SCHEMA = "flute-audio-pitch-v1" as const
/** Previous timbre block (log-Mel + MFCC + RMS/flatness/low-band), kept as dims [0..47]. */
export const FLUTE_TIMBRE_DIM = 48
/** Pitch block appended at [48..61]: voiced, clarity, octaves above C5, 11 note affinities. */
export const FLUTE_PITCH_DIM = 14
export const FLUTE_AUDIO_DIM = FLUTE_TIMBRE_DIM + FLUTE_PITCH_DIM // 62
export const FLUTE_VOICED_IDX = 48
export const FLUTE_CLARITY_IDX = 49
export const FLUTE_OCTAVES_IDX = 50
export const FLUTE_AFFINITY_START_IDX = 51
export const FLUTE_MEL_BANDS = 32
export const FLUTE_MFCC_COUNT = 13

export const FLUTE_ORDERED_NOTES: FluteNoteName[] = [
  "SI",
  "LA",
  "SOL",
  "DO6",
  "RE6",
  "FA",
  "FA#",
  "MI",
  "RE",
  "DO",
  "MI6",
]

export const RECOMMENDED_TAKES_PER_NOTE = 2

export const FLUTE_NOTES_MAP: Record<FluteNoteName, FluteNoteSpec> = {
  SI: {
    note: "SI",
    displayName: "SI",
    handsRequired: 1,
    thumbState: "tapado",
    frontHoles: [true, false, false, false, false, false, false],
    handTip: "Mano Izq arriba: Pulgar trasero tapado + Índice (Hueco 1)",
    difficultyLevel: 1,
  },
  LA: {
    note: "LA",
    displayName: "LA",
    handsRequired: 1,
    thumbState: "tapado",
    frontHoles: [true, true, false, false, false, false, false],
    handTip: "Mano Izq arriba: Pulgar trasero tapado + Huecos 1 y 2",
    difficultyLevel: 1,
  },
  SOL: {
    note: "SOL",
    displayName: "SOL",
    handsRequired: 1,
    thumbState: "tapado",
    frontHoles: [true, true, true, false, false, false, false],
    handTip: "Mano Izq arriba: Pulgar trasero tapado + Huecos 1, 2 y 3",
    difficultyLevel: 1,
  },
  DO6: {
    note: "DO6",
    displayName: "DO Agudo",
    handsRequired: 1,
    thumbState: "tapado",
    frontHoles: [false, true, false, false, false, false, false],
    handTip: "Mano Izq arriba: Pulgar trasero tapado + solo Dedo Medio (Hueco 2)",
    difficultyLevel: 1,
  },
  RE6: {
    note: "RE6",
    displayName: "RE Agudo",
    handsRequired: 1,
    thumbState: "abierto",
    frontHoles: [false, true, false, false, false, false, false],
    handTip: "Mano Izq arriba: Pulgar trasero DESTAPADO (○) + solo Dedo Medio (Hueco 2)",
    difficultyLevel: 1,
  },
  FA: {
    note: "FA",
    displayName: "FA",
    handsRequired: 2,
    thumbState: "tapado",
    frontHoles: [true, true, true, true, false, false, false],
    handTip: "2 Manos: Izquierda (1-3) + Derecha abajo Índice (Hueco 4)",
    difficultyLevel: 3,
  },
  "FA#": {
    note: "FA#",
    displayName: "FA# (Sost.)",
    handsRequired: 2,
    thumbState: "tapado",
    frontHoles: [true, true, true, false, true, true, false],
    handTip: "2 Manos: Izquierda (1-3) + Derecha Hueco 4 libre y Huecos 5-6 tapados",
    difficultyLevel: 3,
  },
  MI: {
    note: "MI",
    displayName: "MI",
    handsRequired: 2,
    thumbState: "tapado",
    frontHoles: [true, true, true, true, true, false, false],
    handTip: "2 Manos: Izquierda (1-3) + Derecha abajo 2 dedos (Huecos 4 y 5)",
    difficultyLevel: 3,
  },
  RE: {
    note: "RE",
    displayName: "RE Grave",
    handsRequired: 2,
    thumbState: "tapado",
    frontHoles: [true, true, true, true, true, true, false],
    handTip: "2 Manos: Izquierda (1-3) + Derecha abajo 3 dedos (Huecos 4, 5 y 6)",
    difficultyLevel: 3,
  },
  DO: {
    note: "DO",
    displayName: "DO Grave",
    handsRequired: 2,
    thumbState: "tapado",
    frontHoles: [true, true, true, true, true, true, true],
    handTip: "2 Manos completas: Los 7 huecos tapados + soplo suave sin chillar",
    difficultyLevel: 3,
  },
  MI6: {
    note: "MI6",
    displayName: "MI Agudo",
    handsRequired: 2,
    thumbState: "medio",
    frontHoles: [true, true, true, true, true, false, false],
    handTip: "2 Manos: Medio Pulgar trasero (◐ portavoz) + Izq (1-3) y Der (4-5)",
    difficultyLevel: 3,
  },
}

export interface FluteVariationSpec {
  id: FluteVariationType
  shortLabel: string
  title: string
  instruction: string
  durationSeconds: number
  isCore: boolean
}

export const FLUTE_VARIATIONS_LIST: FluteVariationSpec[] = [
  {
    id: "sostenida",
    shortLabel: "1. Larga Sostenida (Obligatoria)",
    title: "Toma 1/2: Nota Larga y Estable (4s)",
    instruction: "Mantén la nota continua sin cortar el aire durante 4 segundos.",
    durationSeconds: 4,
    isCore: true,
  },
  {
    id: "rapida",
    shortLabel: "2. Rápida / Staccato (Obligatoria)",
    title: "Toma 2/2: Repeticiones Rápidas (4s)",
    instruction: "Toca la misma nota varias veces rápido (tu-tu-tu-tu) manteniendo los dedos.",
    durationSeconds: 4,
    isCore: true,
  },
  {
    id: "angulo_suave",
    shortLabel: "3. Extra: Ángulo / Suave (Opcional)",
    title: "Toma Extra: Ángulo de Cámara (4s)",
    instruction: "Gira levemente tu postura frente a la cámara mientras tocas la nota.",
    durationSeconds: 4,
    isCore: false,
  },
]

const hzToMel = (f: number) => 2595 * Math.log10(1 + f / 700)
const melToHz = (m: number) => 700 * (10 ** (m / 2595) - 1)

// Precompute Mel filter edge frequencies (32 triangular bands spanning 350..6000)
const MEL_MIN = hzToMel(350)
const MEL_MAX = hzToMel(6000)
const MEL_EDGE_FREQS = Array.from({ length: FLUTE_MEL_BANDS + 2 }, (_, i) =>
  melToHz(MEL_MIN + (i * (MEL_MAX - MEL_MIN)) / (FLUTE_MEL_BANDS + 1))
)

export interface AudioActivityStatus {
  rms: number
  hasSound: boolean
}

/** Lightweight acoustic activity detector (energy only). */
export function measureAudioActivity(analyser: AnalyserNode): AudioActivityStatus {
  const waveform = new Float32Array(analyser.fftSize)
  analyser.getFloatTimeDomainData(waveform)
  let sumSq = 0
  for (let i = 0; i < waveform.length; i++) {
    sumSq += waveform[i] * waveform[i]
  }
  const rms = Math.sqrt(sumSq / Math.max(1, waveform.length))
  return { rms, hasSound: rms >= 0.012 }
}

/**
 * Acoustic feature extractor, schema `flute-audio-pitch-v1` (62 floats):
 * - [0..31]: 32 L2-normalized log-Mel filterbank energies (captures flute note timbre + overtones)
 * - [32..44]: 13 MFCCs (DCT-II c1..c13 of log-Mel, separates woodwind timbre from voice/noise)
 * - [45]: RMS energy (clamped 0..1)
 * - [46]: Spectral flatness (tonal woodwind vs broadband room noise)
 * - [47]: Low-band energy ratio (<420 Hz share, distinguishes chest voice from flute)
 * - [48]: voiced (1 when YIN found a stable pitch in 430..1600 Hz, else 0)
 * - [49]: YIN clarity 0..1 (1 - cumulative mean normalized difference at the chosen lag)
 * - [50]: octaves above C5 = log2(f0 / 523.2511) (0 if unvoiced)
 * - [51..61]: affinity per note in FLUTE_PITCH_NOTE_ORDER = exp(-0.5·(cents/35)²) (0 if unvoiced)
 */
export function extractFluteAudioFeatures(
  analyser: AnalyserNode,
  sampleRate: number
): number[] {
  const binCount = analyser.frequencyBinCount
  const spectrumDb = new Float32Array(binCount)
  const waveform = new Float32Array(analyser.fftSize)
  analyser.getFloatFrequencyData(spectrumDb)
  analyser.getFloatTimeDomainData(waveform)

  let sumSq = 0
  for (let i = 0; i < waveform.length; i++) {
    sumSq += waveform[i] * waveform[i]
  }
  const rms = Math.min(1, Math.sqrt(sumSq / Math.max(1, waveform.length)))

  // Convert dB spectrum to linear power per bin
  const power = new Float64Array(binCount)
  const binWidth = sampleRate / Math.max(1, analyser.fftSize)
  let totalPower = 0
  let lowPower = 0
  let fluteBandLogSum = 0
  let fluteBandPowerSum = 0
  let fluteBandBins = 0

  for (let i = 1; i < binCount; i++) {
    const freq = i * binWidth
    if (freq > 6200) break
    const db = Number.isFinite(spectrumDb[i]) ? Math.max(-120, Math.min(0, spectrumDb[i])) : -120
    const p = 10 ** (db / 10)
    power[i] = p
    totalPower += p
    if (freq < 420) lowPower += p
    if (freq >= 350 && freq <= 6000) {
      fluteBandPowerSum += p
      fluteBandLogSum += Math.log(p + 1e-12)
      fluteBandBins += 1
    }
  }

  // 1. 32 triangular Mel filterbank energies
  const logMel = new Array<number>(FLUTE_MEL_BANDS).fill(0)
  for (let m = 0; m < FLUTE_MEL_BANDS; m++) {
    const fLeft = MEL_EDGE_FREQS[m]
    const fCenter = MEL_EDGE_FREQS[m + 1]
    const fRight = MEL_EDGE_FREQS[m + 2]
    const binStart = Math.max(1, Math.floor(fLeft / binWidth))
    const binEnd = Math.min(binCount - 1, Math.ceil(fRight / binWidth))
    let bandEnergy = 0
    for (let b = binStart; b <= binEnd; b++) {
      const f = b * binWidth
      let weight = 0
      if (f >= fLeft && f <= fCenter && fCenter > fLeft) {
        weight = (f - fLeft) / (fCenter - fLeft)
      } else if (f > fCenter && f <= fRight && fRight > fCenter) {
        weight = (fRight - f) / (fRight - fCenter)
      }
      bandEnergy += power[b] * weight
    }
    logMel[m] = Math.log10(bandEnergy + 1e-10) + 10 // Shift into >= 0 range
  }

  // Normalize log-Mel vector per frame (invariant to mic gain/distance)
  let melMean = 0
  for (let m = 0; m < FLUTE_MEL_BANDS; m++) melMean += logMel[m]
  melMean /= FLUTE_MEL_BANDS
  const centeredMel = logMel.map((v) => v - melMean)
  const melNorm = Math.hypot(...centeredMel)
  const normMel = melNorm > 1e-6 ? centeredMel.map((v) => v / melNorm) : centeredMel.map(() => 0)

  // 2. 13 MFCCs (DCT-II, coefficients k = 1..13)
  const mfccs = new Array<number>(FLUTE_MFCC_COUNT).fill(0)
  const dctScale = Math.sqrt(2 / FLUTE_MEL_BANDS)
  for (let k = 1; k <= FLUTE_MFCC_COUNT; k++) {
    let sum = 0
    for (let n = 0; n < FLUTE_MEL_BANDS; n++) {
      sum += normMel[n] * Math.cos((Math.PI * k * (n + 0.5)) / FLUTE_MEL_BANDS)
    }
    mfccs[k - 1] = dctScale * sum
  }

  // 3. Spectral flatness (tonality vs noise) and low-band energy ratio
  const meanFlutePower = fluteBandBins > 0 ? fluteBandPowerSum / fluteBandBins : 0
  const geoMeanFlutePower = fluteBandBins > 0 ? Math.exp(fluteBandLogSum / fluteBandBins) : 0
  const spectralFlatness =
    meanFlutePower > 1e-12 ? Math.min(1, geoMeanFlutePower / meanFlutePower) : 1
  const lowEnergyRatio = totalPower > 1e-12 ? Math.min(1, lowPower / totalPower) : 0

  const pitch = estimatePitchYin(waveform, sampleRate)
  return [
    ...normMel,
    ...mfccs,
    rms,
    spectralFlatness,
    lowEnergyRatio,
    ...buildPitchFeatures(pitch.hz, pitch.clarity),
  ].map((v) => (Number.isFinite(v) ? v : 0))
}

// ---------------------------------------------------------------------------
// Pitch (f0) estimation — YIN (de Cheveigné & Kawahara, 2002)
// ---------------------------------------------------------------------------

/** Backend note order for the affinity block [51..61]. Do not reorder. */
export const FLUTE_PITCH_NOTE_ORDER: readonly FluteNoteName[] = [
  "DO", "RE", "MI", "FA", "FA#", "SOL", "LA", "SI", "DO6", "RE6", "MI6",
]

/** Equal temperament, A4 = 440 Hz (soprano recorder sounds C5..E6). */
export const FLUTE_NOTE_FREQUENCIES_HZ: Record<FluteNoteName, number> = {
  DO: 523.2511,
  RE: 587.3295,
  MI: 659.2551,
  FA: 698.4565,
  "FA#": 739.9888,
  SOL: 783.9909,
  LA: 880,
  SI: 987.7666,
  DO6: 1046.502,
  RE6: 1174.659,
  MI6: 1318.51,
}

export const FLUTE_PITCH_MIN_HZ = 430
export const FLUTE_PITCH_MAX_HZ = 1600
export const FLUTE_PITCH_MIN_CLARITY = 0.8
export const FLUTE_PITCH_MIN_RMS = 0.012
const YIN_THRESHOLD = 0.15
const AFFINITY_SIGMA_CENTS = 35
const C5_HZ = FLUTE_NOTE_FREQUENCIES_HZ.DO

export interface PitchEstimate {
  /** Fundamental frequency in Hz, or null when unvoiced/unstable. */
  hz: number | null
  /** 1 - CMND at the chosen lag, clamped 0..1. */
  clarity: number
}

/**
 * YIN f0 estimate restricted to 430..1600 Hz: difference function, cumulative mean
 * normalized difference (CMND), absolute threshold 0.15 (falls back to the global minimum)
 * and parabolic interpolation. hz is null when clarity < 0.8 or RMS < 0.012.
 */
export function estimatePitchYin(waveform: Float32Array, sampleRate: number): PitchEstimate {
  const n = waveform.length
  if (!(sampleRate > 0) || !Number.isFinite(sampleRate) || n < 8) return { hz: null, clarity: 0 }

  let sumSq = 0
  for (let i = 0; i < n; i++) sumSq += waveform[i] * waveform[i]
  const rms = Math.sqrt(sumSq / n)

  const tauMin = Math.max(2, Math.floor(sampleRate / FLUTE_PITCH_MAX_HZ))
  const tauMax = Math.min(Math.ceil(sampleRate / FLUTE_PITCH_MIN_HZ), Math.floor(n / 2) - 1)
  if (tauMax <= tauMin + 1) return { hz: null, clarity: 0 }

  // 1. Difference function d(τ) over a fixed window (τ up to tauMax + 1 for interpolation)
  const lastTau = tauMax + 1
  const windowSize = n - lastTau
  const diff = new Float64Array(lastTau + 1)
  for (let tau = 1; tau <= lastTau; tau++) {
    let sum = 0
    for (let j = 0; j < windowSize; j++) {
      const delta = waveform[j] - waveform[j + tau]
      sum += delta * delta
    }
    diff[tau] = sum
  }

  // 2. Cumulative mean normalized difference d'(τ)
  const cmnd = new Float64Array(lastTau + 1)
  cmnd[0] = 1
  let running = 0
  for (let tau = 1; tau <= lastTau; tau++) {
    running += diff[tau]
    cmnd[tau] = running > 1e-12 ? (diff[tau] * tau) / running : 1
  }

  // 3. Absolute threshold (first dip, followed to its local minimum), else global minimum
  let best = -1
  for (let tau = tauMin; tau <= tauMax; tau++) {
    if (cmnd[tau] < YIN_THRESHOLD) {
      while (tau + 1 <= tauMax && cmnd[tau + 1] < cmnd[tau]) tau++
      best = tau
      break
    }
  }
  if (best < 0) {
    best = tauMin
    for (let tau = tauMin + 1; tau <= tauMax; tau++) if (cmnd[tau] < cmnd[best]) best = tau
  }
  const clarity = Math.max(0, Math.min(1, 1 - cmnd[best]))

  // 4. Parabolic interpolation around the chosen lag (on the raw difference function)
  let refinedTau = best
  const a = diff[best - 1]
  const b = diff[best]
  const c = diff[best + 1]
  const denom = a - 2 * b + c
  if (Math.abs(denom) > 1e-12) {
    const shift = (0.5 * (a - c)) / denom
    if (Math.abs(shift) < 1) refinedTau = best + shift
  }
  const hz = sampleRate / refinedTau

  if (
    rms < FLUTE_PITCH_MIN_RMS ||
    clarity < FLUTE_PITCH_MIN_CLARITY ||
    !Number.isFinite(hz) ||
    hz < FLUTE_PITCH_MIN_HZ ||
    hz > FLUTE_PITCH_MAX_HZ
  ) {
    return { hz: null, clarity }
  }
  return { hz, clarity }
}

/** Nearest note of the recorder range and the signed deviation in cents. */
export function nearestFluteNote(hz: number): { note: FluteNoteName; centsOff: number } {
  let note: FluteNoteName = FLUTE_PITCH_NOTE_ORDER[0]
  let centsOff = Number.POSITIVE_INFINITY
  for (const candidate of FLUTE_PITCH_NOTE_ORDER) {
    const c = 1200 * Math.log2(hz / FLUTE_NOTE_FREQUENCIES_HZ[candidate])
    if (Math.abs(c) < Math.abs(centsOff)) {
      note = candidate
      centsOff = c
    }
  }
  return { note, centsOff }
}

/** Pitch block [48..61]: voiced, clarity, octaves above C5, 11 note affinities (14 values). */
export function buildPitchFeatures(hz: number | null, clarity: number): number[] {
  const safeClarity = Number.isFinite(clarity) ? Math.max(0, Math.min(1, clarity)) : 0
  if (hz === null || !Number.isFinite(hz) || hz <= 0) {
    return [0, safeClarity, 0, ...Array<number>(FLUTE_PITCH_NOTE_ORDER.length).fill(0)]
  }
  const affinities = FLUTE_PITCH_NOTE_ORDER.map((note) => {
    const cents = 1200 * Math.log2(hz / FLUTE_NOTE_FREQUENCIES_HZ[note])
    return Math.exp(-0.5 * (cents / AFFINITY_SIGMA_CENTS) ** 2)
  })
  return [1, safeClarity, Math.log2(hz / C5_HZ), ...affinities]
}

// ---------------------------------------------------------------------------
// Capture quality gates (silence gating + pitch agreement)
// ---------------------------------------------------------------------------

export const FLUTE_MAX_FEATURE_FRAMES = 120
export const FLUTE_MIN_PITCH_AGREEMENT = 0.3
export const FLUTE_MIN_VOICED_FRAMES = 3
const PITCH_MATCH_TOLERANCE_CENTS = 60

export function isVoicedAudioFrame(audioFeatures: readonly number[]): boolean {
  return audioFeatures[FLUTE_VOICED_IDX] === 1
}

/** Keeps only voiced frames for flute takes (voice/noise negatives keep all) and caps at 120. */
export function gateFluteFrames<T extends { audio_features: readonly number[] }>(
  frames: readonly T[],
  soundLabel: string
): T[] {
  const kept = soundLabel === "flauta"
    ? frames.filter((frame) => isVoicedAudioFrame(frame.audio_features))
    : [...frames]
  return kept.slice(0, FLUTE_MAX_FEATURE_FRAMES)
}

export interface PitchAgreement {
  voicedFrames: number
  matchingFrames: number
  /** matchingFrames / voicedFrames (0 when nothing is voiced). */
  agreement: number
}

/** Fraction of voiced frames whose detected pitch is the labeled note (±60 cents). */
export function computePitchAgreement(
  audioFrames: readonly (readonly number[])[],
  note: FluteNoteName
): PitchAgreement {
  let voicedFrames = 0
  let matchingFrames = 0
  for (const audio of audioFrames) {
    if (!isVoicedAudioFrame(audio)) continue
    voicedFrames += 1
    const hz = C5_HZ * 2 ** audio[FLUTE_OCTAVES_IDX]
    const nearest = nearestFluteNote(hz)
    if (nearest.note === note && Math.abs(nearest.centsOff) <= PITCH_MATCH_TOLERANCE_CENTS) {
      matchingFrames += 1
    }
  }
  return { voicedFrames, matchingFrames, agreement: voicedFrames > 0 ? matchingFrames / voicedFrames : 0 }
}

/** Spanish rejection message when a flute take does not sound like its labeled note, else null. */
export function pitchAgreementRejection(result: PitchAgreement, note: FluteNoteName): string | null {
  if (result.voicedFrames < FLUTE_MIN_VOICED_FRAMES) {
    return `No se detectó una altura estable de flauta para la nota ${note} (${result.voicedFrames} fotogramas con sonido). Repetí la toma.`
  }
  if (result.agreement < FLUTE_MIN_PITCH_AGREEMENT) {
    return `La altura detectada no corresponde a la nota ${note} (coincidencia ${Math.round(result.agreement * 100)}%). Repetí la toma.`
  }
  return null
}
