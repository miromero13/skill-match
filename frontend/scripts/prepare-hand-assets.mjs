import { mkdir, cp, readFile, writeFile } from "node:fs/promises"
import { createHash } from "node:crypto"

const root = new URL("../", import.meta.url)
const target = new URL("public/models/hand-landmarker/hand_landmarker.task", root)
const source = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
const expected = "fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1"
const digest = bytes => createHash("sha256").update(bytes).digest("hex")
await mkdir(new URL("public/mediapipe/wasm/", root), { recursive: true })
await cp(new URL("node_modules/@mediapipe/tasks-vision/wasm/", root), new URL("public/mediapipe/wasm/", root), { recursive: true })
let bytes
try { bytes = await readFile(target) } catch (error) { if (error.code !== "ENOENT") throw error }
if (!bytes) {
  const response = await fetch(source)
  if (!response.ok) throw new Error(`No se pudo descargar Hand Landmarker: ${response.status}`)
  bytes = Buffer.from(await response.arrayBuffer())
}
if (digest(bytes) !== expected) throw new Error("Checksum incorrecto de Hand Landmarker; no se utilizará el modelo.")
await mkdir(new URL("./", target), { recursive: true })
await writeFile(target, bytes)
console.log("Hand Landmarker v1 y WASM preparados para servir localmente.")
