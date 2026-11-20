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
  | "transicion"

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

export const FLUTE_AUDIO_DIM = 48
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

/** Lightweight acoustic activity detector (energy only, no pitch/Hz). */
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
 * Pure acoustic timbre feature extractor (48 floats, NO pitch/Hz measurement):
 * - [0..31]: 32 L2-normalized log-Mel filterbank energies (captures flute note timbre + overtones)
 * - [32..44]: 13 MFCCs (DCT-II c1..c13 of log-Mel, separates woodwind timbre from voice/noise)
 * - [45]: RMS energy (clamped 0..1)
 * - [46]: Spectral flatness (tonal woodwind vs broadband room noise)
 * - [47]: Low-band energy ratio (<420 Hz share, distinguishes chest voice from flute)
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

  return [...normMel, ...mfccs, rms, spectralFlatness, lowEnergyRatio].map((v) =>
    Number.isFinite(v) ? v : 0
  )
}
