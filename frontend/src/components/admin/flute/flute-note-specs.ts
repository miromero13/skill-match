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
  hz: number
  handsRequired: 1 | 2
  /** Back thumb hole state */
  thumbState: "tapado" | "abierto" | "medio"
  /** 7 front holes from top (1-3 Left Hand, 4-7 Right Hand) */
  frontHoles: [boolean, boolean, boolean, boolean, boolean, boolean, boolean]
  handTip: string
  difficultyLevel: 1 | 3
}

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
    hz: 987.77,
    handsRequired: 1,
    thumbState: "tapado",
    frontHoles: [true, false, false, false, false, false, false],
    handTip: "Mano Izq arriba: Pulgar trasero tapado + Índice (Hueco 1)",
    difficultyLevel: 1,
  },
  LA: {
    note: "LA",
    displayName: "LA",
    hz: 880.0,
    handsRequired: 1,
    thumbState: "tapado",
    frontHoles: [true, true, false, false, false, false, false],
    handTip: "Mano Izq arriba: Pulgar trasero tapado + Huecos 1 y 2",
    difficultyLevel: 1,
  },
  SOL: {
    note: "SOL",
    displayName: "SOL",
    hz: 783.99,
    handsRequired: 1,
    thumbState: "tapado",
    frontHoles: [true, true, true, false, false, false, false],
    handTip: "Mano Izq arriba: Pulgar trasero tapado + Huecos 1, 2 y 3",
    difficultyLevel: 1,
  },
  DO6: {
    note: "DO6",
    displayName: "DO Agudo",
    hz: 1046.5,
    handsRequired: 1,
    thumbState: "tapado",
    frontHoles: [false, true, false, false, false, false, false],
    handTip: "Mano Izq arriba: Pulgar trasero tapado + solo Dedo Medio (Hueco 2)",
    difficultyLevel: 1,
  },
  RE6: {
    note: "RE6",
    displayName: "RE Agudo",
    hz: 1174.66,
    handsRequired: 1,
    thumbState: "abierto",
    frontHoles: [false, true, false, false, false, false, false],
    handTip: "Mano Izq arriba: Pulgar trasero DESTAPADO (○) + solo Dedo Medio (Hueco 2)",
    difficultyLevel: 1,
  },
  FA: {
    note: "FA",
    displayName: "FA",
    hz: 698.46,
    handsRequired: 2,
    thumbState: "tapado",
    frontHoles: [true, true, true, true, false, false, false],
    handTip: "2 Manos: Izquierda (1-3) + Derecha abajo Índice (Hueco 4)",
    difficultyLevel: 3,
  },
  "FA#": {
    note: "FA#",
    displayName: "FA# (Sost.)",
    hz: 739.99,
    handsRequired: 2,
    thumbState: "tapado",
    frontHoles: [true, true, true, false, true, true, false],
    handTip: "2 Manos: Izquierda (1-3) + Derecha Hueco 4 libre y Huecos 5-6 tapados",
    difficultyLevel: 3,
  },
  MI: {
    note: "MI",
    displayName: "MI",
    hz: 659.25,
    handsRequired: 2,
    thumbState: "tapado",
    frontHoles: [true, true, true, true, true, false, false],
    handTip: "2 Manos: Izquierda (1-3) + Derecha abajo 2 dedos (Huecos 4 y 5)",
    difficultyLevel: 3,
  },
  RE: {
    note: "RE",
    displayName: "RE Grave",
    hz: 587.33,
    handsRequired: 2,
    thumbState: "tapado",
    frontHoles: [true, true, true, true, true, true, false],
    handTip: "2 Manos: Izquierda (1-3) + Derecha abajo 3 dedos (Huecos 4, 5 y 6)",
    difficultyLevel: 3,
  },
  DO: {
    note: "DO",
    displayName: "DO Grave",
    hz: 523.25,
    handsRequired: 2,
    thumbState: "tapado",
    frontHoles: [true, true, true, true, true, true, true],
    handTip: "2 Manos completas: Los 7 huecos tapados + soplo suave sin chillar",
    difficultyLevel: 3,
  },
  MI6: {
    note: "MI6",
    displayName: "MI Agudo",
    hz: 1318.51,
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

export interface FluteAudioAnalysis {
  hz: number | null
  isFluteTimbre: boolean
  rejectionReason: "silencio" | "voz_o_ruido" | null
  spectralPurity: number
}

/**
 * Analyzes both time-domain autocorrelation AND FFT spectral purity to detect
 * real flute notes (495 Hz - 1450 Hz) while rejecting human voice (which has
 * strong fundamental/chest energy in 90-440 Hz and wide formant spread).
 */
export function analyzeFluteAudioFrame(
  analyser: AnalyserNode,
  sampleRate: number
): FluteAudioAnalysis {
  const bufferLength = analyser.fftSize
  const timeData = new Float32Array(bufferLength)
  analyser.getFloatTimeDomainData(timeData)

  let sumSq = 0
  for (let i = 0; i < bufferLength; i++) {
    sumSq += timeData[i] * timeData[i]
  }
  const rms = Math.sqrt(sumSq / bufferLength)
  if (rms < 0.015) {
    return {
      hz: null,
      isFluteTimbre: false,
      rejectionReason: "silencio",
      spectralPurity: 0,
    }
  }

  // 1. Check frequency spectrum to separate pure flute whistle from human voice
  const freqBinCount = analyser.frequencyBinCount
  const freqData = new Uint8Array(freqBinCount)
  analyser.getByteFrequencyData(freqData)
  const binHz = sampleRate / (freqBinCount * 2)

  // Low voice fundamental band: 95 Hz - 445 Hz (Soprano recorder lowest note DO5 is 523 Hz)
  const voiceLowStart = Math.max(1, Math.floor(95 / binHz))
  const voiceLowEnd = Math.min(freqBinCount - 1, Math.floor(445 / binHz))
  let voiceLowSum = 0
  let voiceLowMax = 0
  for (let b = voiceLowStart; b <= voiceLowEnd; b++) {
    voiceLowSum += freqData[b]
    if (freqData[b] > voiceLowMax) voiceLowMax = freqData[b]
  }
  const voiceLowAvg = voiceLowSum / Math.max(1, voiceLowEnd - voiceLowStart + 1)

  // Flute fundamental band: 490 Hz - 1480 Hz (DO5=523 Hz up to MI6=1319 Hz)
  const fluteStart = Math.max(1, Math.floor(490 / binHz))
  const fluteEnd = Math.min(freqBinCount - 1, Math.floor(1480 / binHz))
  let fluteSum = 0
  let flutePeakVal = 0
  let flutePeakBin = fluteStart
  for (let b = fluteStart; b <= fluteEnd; b++) {
    fluteSum += freqData[b]
    if (freqData[b] > flutePeakVal) {
      flutePeakVal = freqData[b]
      flutePeakBin = b
    }
  }
  const fluteAvg = fluteSum / Math.max(1, fluteEnd - fluteStart + 1)

  // Calculate narrow-band peak concentration (a flute concentrates energy in 1 narrow peak;
  // human voice spreads formants across many bins and has strong <445Hz chest energy)
  let narrowPeakSum = 0
  for (
    let b = Math.max(fluteStart, flutePeakBin - 2);
    b <= Math.min(fluteEnd, flutePeakBin + 2);
    b++
  ) {
    narrowPeakSum += freqData[b]
  }
  const narrowPeakAvg = narrowPeakSum / 5
  const crestRatio = fluteAvg > 0 ? narrowPeakAvg / fluteAvg : 0

  // 2. Autocorrelation across 100 Hz - 1550 Hz to find true fundamental period
  // (If someone speaks/sings, their true fundamental period will be in 100-440 Hz!)
  const minLag = Math.max(2, Math.floor(sampleRate / 1550))
  const maxLag = Math.min(Math.floor(bufferLength / 2), Math.floor(sampleRate / 110))

  let bestLag = -1
  let bestCorr = 0
  for (let lag = minLag; lag <= maxLag; lag++) {
    let corr = 0
    for (let i = 0; i < bufferLength - lag; i++) {
      corr += timeData[i] * timeData[i + lag]
    }
    if (corr > bestCorr) {
      bestCorr = corr
      bestLag = lag
    }
  }

  const normalizedCorr = bestCorr / (sumSq + 1e-6)
  const rawPitchHz = bestLag > 0 ? sampleRate / bestLag : 0

  // Reject human voice / background noise:
  // - True fundamental pitch < 485 Hz (human speech/singing fundamental)
  // - Low voice band (<445 Hz) has comparable or stronger peak/average than the flute band
  // - Low spectral crest factor (broadband voice formants or room noise instead of pure flute whistle)
  // - Low periodicity correlation
  const hasStrongVoiceFundamental =
    rawPitchHz < 485 ||
    voiceLowMax > flutePeakVal * 0.82 ||
    voiceLowAvg > fluteAvg * 0.9
  const isPureTone = crestRatio >= 1.95 && normalizedCorr >= 0.55 && flutePeakVal >= 75

  if (hasStrongVoiceFundamental || !isPureTone) {
    return {
      hz: rawPitchHz > 0 ? Math.round(rawPitchHz) : null,
      isFluteTimbre: false,
      rejectionReason: "voz_o_ruido",
      spectralPurity: Math.round(Math.min(1, crestRatio / 3) * 100),
    }
  }

  const finalHz = Math.round(rawPitchHz)
  return {
    hz: finalHz,
    isFluteTimbre: true,
    rejectionReason: null,
    spectralPurity: Math.round(Math.min(1, crestRatio / 3) * 100),
  }
}

/** Shared capture/inference layout: 24 linear 0–6kHz energy bands,
 * pitch/1500, spectral crest, low-band share, RMS. Never discard negatives. */
export function extractFluteAudioFeatures(analyser: AnalyserNode, sampleRate: number): number[] {
  const spectrum = new Float32Array(analyser.frequencyBinCount)
  const waveform = new Float32Array(analyser.fftSize)
  analyser.getFloatFrequencyData(spectrum)
  analyser.getFloatTimeDomainData(waveform)
  const bands = Array<number>(24).fill(0)
  let total = 0
  let low = 0
  let peak = 0
  let bins = 0
  for (let i = 1; i < spectrum.length; i++) {
    const hz = i * sampleRate / analyser.fftSize
    if (hz >= 6000) break
    const energy = Number.isFinite(spectrum[i]) ? 10 ** (spectrum[i] / 10) : 0
    bands[Math.floor(hz / 250)] += energy
    total += energy
    peak = Math.max(peak, energy)
    if (hz < 445) low += energy
    bins++
  }
  const rms = Math.sqrt(waveform.reduce((sum, v) => sum + v * v, 0) / waveform.length)
  const pitch = analyzeFluteAudioFrame(analyser, sampleRate).hz ?? 0
  return [...bands.map(v => total ? v / total : 0), pitch / 1500,
    total ? peak / (total / Math.max(1, bins)) : 0, total ? low / total : 0, rms]
}

export function detectFlutePitchHz(
  analyser: AnalyserNode,
  sampleRate: number
): number | null {
  const analysis = analyzeFluteAudioFrame(analyser, sampleRate)
  return analysis.isFluteTimbre ? analysis.hz : null
}

export function findClosestFluteNote(hz: number): {
  note: FluteNoteName
  targetHz: number
  diffHz: number
  isInTune: boolean
} {
  let closest: FluteNoteName = "SOL"
  let minDiff = Infinity

  for (const noteName of FLUTE_ORDERED_NOTES) {
    const spec = FLUTE_NOTES_MAP[noteName]
    const diff = Math.abs(spec.hz - hz)
    if (diff < minDiff) {
      minDiff = diff
      closest = noteName
    }
  }

  const targetHz = Math.round(FLUTE_NOTES_MAP[closest].hz)
  return {
    note: closest,
    targetHz,
    diffHz: Math.round(minDiff),
    // Strict tuning tolerance: within 28 Hz of target note
    isInTune: minDiff <= 28,
  }
}

export interface FluteHandsVisualAnalysis {
  cameraReady: boolean
  brightness: number
  leftHandDetected: boolean
  rightHandDetected: boolean
  leftHandSkinPct: number
  rightHandSkinPct: number
}

/**
 * Inspects the live camera frame in the two vertical hand zones where the flute
 * is held:
 * - Upper Zone (Mano Izquierda - Huecos 1-3): center x [35%..65%], y [42%..64%]
 * - Lower Zone (Mano Derecha - Huecos 4-7): center x [35%..65%], y [65%..88%]
 * Compares skin-tone presence (YCbCr + RGB rules) and local edge/finger contrast
 * against the outer lateral background so an empty background or turned-off camera
 * is never reported as "hands detected".
 */
export function analyzeFluteHandsInVideo(
  video: HTMLVideoElement | null,
  canvas: HTMLCanvasElement | null
): FluteHandsVisualAnalysis {
  if (
    !video ||
    !canvas ||
    video.readyState < 2 ||
    video.videoWidth === 0 ||
    video.videoHeight === 0
  ) {
    return {
      cameraReady: false,
      brightness: 0,
      leftHandDetected: false,
      rightHandDetected: false,
      leftHandSkinPct: 0,
      rightHandSkinPct: 0,
    }
  }

  const ctx = canvas.getContext("2d")
  if (!ctx) {
    return {
      cameraReady: false,
      brightness: 0,
      leftHandDetected: false,
      rightHandDetected: false,
      leftHandSkinPct: 0,
      rightHandSkinPct: 0,
    }
  }

  const w = 96
  const h = 72
  canvas.width = w
  canvas.height = h
  ctx.drawImage(video, 0, 0, w, h)
  const data = ctx.getImageData(0, 0, w, h).data

  let totalLum = 0
  for (let i = 0; i < data.length; i += 4) {
    totalLum += 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2]
  }
  const avgBrightness = Math.round(totalLum / (w * h))

  if (avgBrightness < 25) {
    return {
      cameraReady: true,
      brightness: avgBrightness,
      leftHandDetected: false,
      rightHandDetected: false,
      leftHandSkinPct: 0,
      rightHandSkinPct: 0,
    }
  }

  const isSkinAndFingerPixel = (r: number, g: number, b: number): boolean => {
    // YCbCr skin chrominance bounds + RGB dominance
    const cb = 128 - 0.168736 * r - 0.331264 * g + 0.5 * b
    const cr = 128 + 0.5 * r - 0.418688 * g - 0.081312 * b
    const rgbSkin =
      r > 75 &&
      g > 35 &&
      b > 18 &&
      r > g &&
      r > b &&
      Math.max(r, g, b) - Math.min(r, g, b) > 15 &&
      Math.abs(r - g) > 10
    const ycbcrSkin = cr >= 133 && cr <= 178 && cb >= 75 && cb <= 130
    return rgbSkin && ycbcrSkin
  }

  const measureZone = (
    x0Pct: number,
    x1Pct: number,
    y0Pct: number,
    y1Pct: number
  ): { skinPct: number; edgeContrast: number; meanLum: number } => {
    const x0 = Math.floor(w * x0Pct)
    const x1 = Math.floor(w * x1Pct)
    const y0 = Math.floor(h * y0Pct)
    const y1 = Math.floor(h * y1Pct)

    let skinCount = 0
    let totalPixels = 0
    let edgeSum = 0
    let lumSum = 0

    for (let y = y0; y < y1; y++) {
      for (let x = x0; x < x1; x++) {
        const idx = (y * w + x) * 4
        const r = data[idx]
        const g = data[idx + 1]
        const b = data[idx + 2]
        const lum = 0.299 * r + 0.587 * g + 0.114 * b
        lumSum += lum
        if (isSkinAndFingerPixel(r, g, b)) {
          skinCount += 1
        }
        if (x + 1 < x1) {
          const nextIdx = (y * w + (x + 1)) * 4
          const nextLum =
            0.299 * data[nextIdx] +
            0.587 * data[nextIdx + 1] +
            0.114 * data[nextIdx + 2]
          edgeSum += Math.abs(lum - nextLum)
        }
        totalPixels += 1
      }
    }

    const count = Math.max(1, totalPixels)
    return {
      skinPct: Math.round((skinCount / count) * 100),
      edgeContrast: edgeSum / count,
      meanLum: lumSum / count,
    }
  }

  // Background reference on left & right margins (where hands aren't)
  const bgLeft = measureZone(0.04, 0.22, 0.45, 0.85)
  const bgRight = measureZone(0.78, 0.96, 0.45, 0.85)
  const bgSkinBaseline = (bgLeft.skinPct + bgRight.skinPct) / 2

  // Upper flute zone: Mano Izquierda (Huecos 1-3, below mouth/chin)
  const upperZone = measureZone(0.34, 0.66, 0.44, 0.66)
  // Lower flute zone: Mano Derecha (Huecos 4-7, lower chest)
  const lowerZone = measureZone(0.34, 0.66, 0.66, 0.90)

  // A hand is truly present in a zone only if:
  // 1) It has enough skin pixels (>= 14%)
  // 2) It has meaningfully more skin/finger texture than the background wall (>= bg + 8%)
  // 3) It has finger/flute edge detail (edgeContrast >= 7.5)
  const leftHandDetected =
    upperZone.skinPct >= 14 &&
    upperZone.skinPct >= bgSkinBaseline + 7 &&
    upperZone.edgeContrast >= 7.0

  const rightHandDetected =
    lowerZone.skinPct >= 14 &&
    lowerZone.skinPct >= bgSkinBaseline + 7 &&
    lowerZone.edgeContrast >= 7.0

  return {
    cameraReady: true,
    brightness: avgBrightness,
    leftHandDetected,
    rightHandDetected,
    leftHandSkinPct: upperZone.skinPct,
    rightHandSkinPct: lowerZone.skinPct,
  }
}
