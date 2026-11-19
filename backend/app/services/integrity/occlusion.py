"""Face and mouth occlusion from pixels (T7 / S7).

A frame is judged against the trial's own reference (built from its first clean frontal frames), never against
absolute skin colours, so skin tone and lighting are normalized per person.

Measurements (``measure``), on the YCrCb image with the geometry of the face (eyes, nose, mouth corners):
  * skin: median chroma (Cr, Cb) of the forehead and both cheek patches of the same frame;
  * for the eye band, the nose and the mouth: chroma distance to that skin and edge energy of the luma patch
    (resized to a fixed size, blurred, mean Sobel magnitude).

Judgement (``judge``), per region R with reference distance d0 and edge energy e0:
  anomalous(R) = (e <= 0.20 e0) or (e <= 0.35 e0 and |d - d0| >= 12) or |d - d0| >= 30      [only if e0 >= 1.5]
A region that lost its texture is covered by something smooth (hand, mask, paper); a hand has the skin's
chroma, a mask or paper does not. With n anomalous regions among {eyes, nose, mouth}:
  skin_shift = the skin patches themselves moved >= 18 in (Cr, Cb) from the reference (black or white cover)
  support    = detector collapse (MediaPipe sees a face, YuNet found nothing or its confidence collapsed)
               or an identity similarity drop (SFace under the trial's matching level)
  face  = n == 3 or (n >= 2 and (eyes or support)) or (n >= 1 and (skin_shift or support)) or (skin_shift and support)
  mouth = mouth anomalous and not face          (nose + mouth with the eyes visible is a mask: mouth only)
"""
from dataclasses import dataclass
from typing import Mapping, Optional

import cv2
import numpy as np

from app.services.integrity import thresholds as t
from app.services.integrity.models import FrameOcclusion

REGIONS = ("eyes", "nose", "mouth")


@dataclass(frozen=True)
class OcclusionMeasure:
    skin: tuple[float, float]  # median (Cr, Cb) of forehead and cheeks
    distance: Mapping[str, float]  # region -> chroma distance to the skin
    edge: Mapping[str, float]  # region -> edge energy


def _patch(plane: np.ndarray, cx: float, cy: float, w: float, h: float) -> Optional[np.ndarray]:
    height, width = plane.shape[:2]
    x1, x2 = int(round(max(cx - w / 2, 0))), int(round(min(cx + w / 2, width)))
    y1, y2 = int(round(max(cy - h / 2, 0))), int(round(min(cy + h / 2, height)))
    if x2 - x1 < 4 or y2 - y1 < 3:
        return None
    return plane[y1:y2, x1:x2]


def _edge_energy(luma: np.ndarray) -> float:
    small = cv2.resize(luma, t.OCC_PATCH_SIZE, interpolation=cv2.INTER_AREA).astype(np.float32)
    small = cv2.GaussianBlur(small, (3, 3), 0.8)
    return float(np.hypot(cv2.Sobel(small, cv2.CV_32F, 1, 0, ksize=3), cv2.Sobel(small, cv2.CV_32F, 0, 1, ksize=3)).mean())


def measure(image: np.ndarray, geometry: tuple[float, ...]) -> Optional[OcclusionMeasure]:
    """Patch statistics for a face whose (right eye, left eye, nose, right and left mouth corner) are ``geometry``."""
    rx, ry, lx, ly, nx, ny, rmx, rmy, lmx, lmy = geometry
    ed = float(np.hypot(lx - rx, ly - ry))
    if not np.isfinite(ed) or ed < t.OCC_MIN_EYE_DISTANCE_PX:
        return None
    em_x, em_y = (rx + lx) / 2.0, (ry + ly) / 2.0
    mouth_x, mouth_y = (rmx + lmx) / 2.0, (rmy + lmy) / 2.0
    mouth_w = max(float(np.hypot(lmx - rmx, lmy - rmy)) * 1.4, 0.8 * ed)
    ycc = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)
    boxes = {
        "forehead": (em_x, em_y - 0.62 * ed, 0.9 * ed, 0.3 * ed),
        "cheek_a": (em_x - 0.62 * ed, em_y + 0.6 * ed, 0.3 * ed, 0.3 * ed),
        "cheek_b": (em_x + 0.62 * ed, em_y + 0.6 * ed, 0.3 * ed, 0.3 * ed),
        "eyes": (em_x, em_y, 1.5 * ed, 0.35 * ed),
        "nose": (nx, ny - 0.1 * ed, 0.4 * ed, 0.5 * ed),
        "mouth": (mouth_x, mouth_y, mouth_w, 0.45 * ed),
    }
    patches = {name: _patch(ycc, *box) for name, box in boxes.items()}
    if any(patch is None for patch in patches.values()):
        return None
    chroma = {name: (float(p[..., 1].mean()), float(p[..., 2].mean())) for name, p in patches.items() if p is not None}
    skin = tuple(float(np.median([chroma[n][i] for n in ("forehead", "cheek_a", "cheek_b")])) for i in (0, 1))
    return OcclusionMeasure(
        skin=(skin[0], skin[1]),
        distance={r: float(np.hypot(chroma[r][0] - skin[0], chroma[r][1] - skin[1])) for r in REGIONS},
        edge={r: _edge_energy(patches[r][..., 0]) for r in REGIONS if patches[r] is not None},
    )


def new_reference(m: OcclusionMeasure) -> dict[str, float]:
    ref: dict[str, float] = {"n": 1.0, "skin_cr": m.skin[0], "skin_cb": m.skin[1]}
    for r in REGIONS:
        ref[f"{r}_d"], ref[f"{r}_e"] = m.distance[r], m.edge[r]
    return ref


def fold_reference(
    ref: Optional[Mapping[str, float]], m: OcclusionMeasure, similarity: Optional[float] = None,
    yunet_score: Optional[float] = None,
) -> dict[str, float]:
    """Folds a clean frame into the reference: a plain mean while it is being built, then a slow EMA."""
    base = dict(ref) if ref else new_reference(m)
    current = new_reference(m)
    n = base["n"]
    weight = (1.0 / (n + 1.0)) if n < t.OCC_REF_MIN_SAMPLES else t.OCC_REF_ALPHA
    if ref:
        for key, value in current.items():
            if key != "n":
                base[key] = (1.0 - weight) * base[key] + weight * value
        base["n"] = n + 1.0
    for key, value in (("sim", similarity), ("yunet", yunet_score)):
        if value is not None:
            base[key] = value if key not in base else (1.0 - weight) * base[key] + weight * value
    return base


def anomalous_regions(m: OcclusionMeasure, ref: Mapping[str, float]) -> list[str]:
    found = []
    for r in REGIONS:
        e0, d0 = ref[f"{r}_e"], ref[f"{r}_d"]
        if e0 < t.OCC_EDGE_MIN_REF:
            continue
        ratio, delta = m.edge[r] / e0, abs(m.distance[r] - d0)
        if (ratio <= t.OCC_EDGE_COLLAPSE_STRONG or (ratio <= t.OCC_EDGE_COLLAPSE and delta >= t.OCC_CHROMA_DELTA)
                or delta >= t.OCC_CHROMA_STRONG):
            found.append(r)
    return found


def judge(
    m: OcclusionMeasure, ref: Mapping[str, float], similarity: Optional[float] = None,
    yunet_score: Optional[float] = None, mediapipe_saw_face: bool = False, yunet_ran: bool = False,
) -> FrameOcclusion:
    regions = anomalous_regions(m, ref)
    skin_shift = float(np.hypot(m.skin[0] - ref["skin_cr"], m.skin[1] - ref["skin_cb"])) >= t.OCC_SKIN_SHIFT
    usual = ref.get("yunet")
    collapse = mediapipe_saw_face and yunet_ran and (
        yunet_score is None
        or (yunet_score < t.OCC_YUNET_COLLAPSE_SCORE and usual is not None
            and usual - yunet_score >= t.OCC_YUNET_COLLAPSE_DROP)
    )
    sim_drop = similarity is not None and "sim" in ref and ref["sim"] - similarity >= t.OCC_SIM_DROP
    support = collapse or sim_drop
    n = len(regions)
    face = (
        n == 3 or (n >= 2 and ("eyes" in regions or support)) or (n >= 1 and (skin_shift or support))
        or (skin_shift and support)
    )
    mouth = "mouth" in regions and not face
    signals = tuple(regions) + tuple(name for name, on in (("skin_shift", skin_shift), ("detector", collapse),
                                                          ("identity", sim_drop)) if on)
    return FrameOcclusion(face=face, mouth=mouth, measured=True, signals=signals)


def is_clean(occlusion: FrameOcclusion) -> bool:
    return occlusion.measured and not occlusion.signals

