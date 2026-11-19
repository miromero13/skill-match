#!/usr/bin/env node
/**
 * Provisions the self-hosted MediaPipe assets used by the in-browser gaze tracking (no CDN at runtime):
 *
 *   public/mediapipe/wasm/*                 copied from node_modules/@mediapipe/tasks-vision/wasm
 *   public/mediapipe/face_landmarker.task   the same SHA-256-pinned model the backend uses
 *
 * The model comes from the backend weights when present and valid (no network); otherwise it is downloaded
 * over HTTPS and verified against the pin. An existing file with the wrong hash is never overwritten.
 *
 * Flags:  --wasm-only   copy the wasm files only (offline safe; used by `postinstall`)
 *         --verify-only check the installed files without copying or downloading
 *         --soft        a model that cannot be installed is a warning, not a failure (predev/prebuild)
 */
import { createHash } from "node:crypto"
import { copyFileSync, existsSync, mkdirSync, readFileSync, readdirSync, renameSync, writeFileSync } from "node:fs"
import { dirname, join, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..")
const target = join(root, "public", "mediapipe")
const wasmSource = join(root, "node_modules", "@mediapipe", "tasks-vision", "wasm")
const backendModel = resolve(root, "..", "backend", "app", "models", "weights", "face_landmarker.task")

// Same artifact and pin as backend/scripts/install_vision_models.py
const MODEL_NAME = "face_landmarker.task"
const MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
const MODEL_SHA256 = "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff"
const MAX_MODEL_BYTES = 60_000_000

const args = new Set(process.argv.slice(2))
const wasmOnly = args.has("--wasm-only")
const verifyOnly = args.has("--verify-only")
const soft = args.has("--soft")

const sha256 = (data) => createHash("sha256").update(data).digest("hex")

function installWasm() {
  if (!existsSync(wasmSource)) {
    throw new Error("Falta @mediapipe/tasks-vision en node_modules: ejecutá `npm install` primero.")
  }
  const files = readdirSync(wasmSource).filter((name) => name.startsWith("vision_wasm"))
  if (!files.length) throw new Error(`No hay archivos wasm de MediaPipe en ${wasmSource}`)
  if (verifyOnly) {
    const missing = files.filter((name) => !existsSync(join(target, "wasm", name)))
    if (missing.length) throw new Error(`Faltan archivos wasm en public/mediapipe/wasm: ${missing.join(", ")}`)
    return files.length
  }
  mkdirSync(join(target, "wasm"), { recursive: true })
  for (const name of files) copyFileSync(join(wasmSource, name), join(target, "wasm", name))
  return files.length
}

async function installModel() {
  const destination = join(target, MODEL_NAME)
  if (existsSync(destination)) {
    if (sha256(readFileSync(destination)) !== MODEL_SHA256)
      throw new Error(`Se rechaza sobrescribir un ${MODEL_NAME} existente con un hash distinto al fijado.`)
    return "ya instalado"
  }
  if (verifyOnly) throw new Error(`Falta public/mediapipe/${MODEL_NAME}; ejecutá \`npm run prepare-vision\`.`)
  mkdirSync(target, { recursive: true })
  let data = null
  let origin = ""
  if (existsSync(backendModel)) {
    const local = readFileSync(backendModel)
    if (sha256(local) === MODEL_SHA256) {
      data = local
      origin = "copiado de backend/app/models/weights"
    }
  }
  if (!data) {
    const response = await fetch(MODEL_URL, { redirect: "follow", signal: AbortSignal.timeout(60_000) })
    if (!response.ok || !response.url.startsWith("https://")) throw new Error(`Descarga rechazada (${response.status}).`)
    data = Buffer.from(await response.arrayBuffer())
    if (data.length > MAX_MODEL_BYTES) throw new Error("La descarga supera el límite de tamaño fijado.")
    if (sha256(data) !== MODEL_SHA256) throw new Error("El modelo descargado no coincide con el SHA-256 fijado.")
    origin = "descargado"
  }
  const staging = `${destination}.part`
  writeFileSync(staging, data)
  renameSync(staging, destination)
  return origin
}

try {
  console.log(`[vision-assets] wasm: ${installWasm()} archivos en public/mediapipe/wasm`)
  if (!wasmOnly) {
    try {
      console.log(`[vision-assets] ${MODEL_NAME}: ${await installModel()}`)
    } catch (error) {
      if (!soft) throw error
      console.warn(`[vision-assets] aviso: ${error.message} El seguimiento de mirada del navegador quedará deshabilitado.`)
    }
  }
} catch (error) {
  console.error(`[vision-assets] error: ${error.message}`)
  process.exit(1)
}
