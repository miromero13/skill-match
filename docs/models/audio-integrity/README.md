# Modelos locales de hablantes — SM-44

**Uso experimental, solo inferencia propia.** No se identifican personas ni aplicaciones de llamadas. Los modelos deben existir antes de atender solicitudes; si faltan, la calibración falla con503. No hay descarga automática durante una solicitud.

## Instalación explícita

Desde la raíz del proyecto:

```bash
cd backend
uv sync --locked
.venv/bin/python scripts/install_calibration_audio_models.py
.venv/bin/python scripts/install_calibration_audio_models.py --verify-only
```

También puede usarse el entorno instalado mediante `pip install -r requirements.txt`. La inferencia requiere `sherpa-onnx==2.0.1` y su dependencia nativa `sherpa-onnx-core`; las pruebas aquí se ejecutaron con2.0.1 de ambos.

El aprovisionador descarga los dos artefactos oficiales mediante HTTPS, verifica SHA256 antes de publicarlos y limita tamaños. Del archivo comprimido solo lee el miembro regular `model.onnx`; no usa extracción general. **Nunca sobrescribe archivos existentes**: ante archivos corruptos, informa un error para una recuperación manual autorizada. `--verify-only` no hace red ni escribe archivos. La instalación puede reanudarse si solo existe uno de los dos archivos válidos.

Los modelos se instalan en `backend/app/models/weights/audio-integrity/`. En despliegue, incluirlos como artefactos o en un volumen de solo lectura antes de iniciar el backend; conservar estos avisos. La aplicación verifica hashes también antes de la inferencia. Reiniciar el backend y recargar el frontend después de actualizar la dependencia/contrato. Esto no instala/aplica migraciones ni ejecuta seeds.

## Artefactos y procedencia

| Archivo instalado | Tamaño | SHA256 |
|---|---:|---|
| `speaker_segmentation.onnx` | 5992913 bytes | `220ad67ca923bef2fa91f2390c786097bf305bceb5e261d4af67b38e938e1079` |
| `speaker_embedding.onnx` | 39593761 bytes | `1a331345f04805badbb495c775a6ddffcdd1a732567d5ec8b3d5749e3c7a5e4b` |

Fuentes:

- [Pyannote segmentation3.0, distribución sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2). Archivo comprimido SHA256 `24615ee884c897d9d2ba09bb4d30da6bb1b15e685065962db5b02e76e4996488`.
- [3D-Speaker ERes2Net16kHz, distribución sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx). El segmento `speaker-recongition-models` conserva la grafía del distribuidor.
- [Ejemplo oficial de diarización offline](https://github.com/k2-fsa/sherpa-onnx/blob/master/python-api-examples/offline-speaker-diarization.py).

`manifest.json` conserva URLs/hashes de los materiales de preparación y del audio público usado en ensayos. No contiene audio privado del miembro. Los archivos grandes se aprovisionan separadamente; no asumir que están versionados en Git.

## Avisos y límites de licencia

- `SEGMENTATION-LICENSE.txt`: MIT, copyright2022 CNRS, incluido en el paquete de segmentación distribuido.
- `3DSPEAKER-LICENSE.txt`: Apache2.0 obtenido del [repositorio3D-Speaker](https://github.com/modelscope/3D-Speaker/blob/main/LICENSE).

La licencia del runtime y la de los modelos son distintas. Se preservó la licencia del proyecto3D-Speaker como procedencia; esto no constituye una revisión legal independiente ni una afirmación adicional sobre términos particulares no publicados en la ficha del peso convertido. No se eligió el modelo Revai de licencia no comercial. Revisar la distribución/uso antes de publicar un producto; no se autoriza publicación por instalar estos archivos.

## Evidencia y límites técnicos

- Un audio público56.86s con varios hablantes fue rechazado por agrupamiento múltiple mediante inferencia nativa real.
- Una mezcla local8s de dos fragmentos produjo dos segmentos superpuestos y rechazo específico. Los fragmentos se seleccionaron de la muestra pública según la segmentación del propio modelo; no es evaluación independiente ni un conjunto etiquetado de eficacia.
- Los ensayos no prueban diarización correcta en todas las frases cortas, español, dispositivos o grupos demográficos. El artefacto de embeddings se distribuye con nombre `zh-cn`; la calibración local aún necesita evaluar su adecuación al español.
- La correspondencia de boca usa heurísticas OpenCV/YuNet/SFace existentes, no este modelo de audio ni lectura semántica de labios. Puede haber falsos positivos/negativos.

Ver [contrato, recorrido, privacidad y pruebas manuales pendientes](../../evaluation-calibration.md). No presentar estos controles como validación PAD, reconocimiento de identidad de voz o garantía contra una llamada.
