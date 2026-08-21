"""
Rasch (IRT-1PL) modeli — parametrlarni baholash.

Asosiy formula (SRS 7-bo'lim):

        P(x = 1 | theta, b) = exp(theta - b) / (1 + exp(theta - b))

bu yerda:
  * `theta` — ishtirokchining qobiliyati (logit shkalasida);
  * `b`     — savolning qiyinligi (logit shkalasida).

Modulda ikkita asosiy vazifa bajariladi:
  1. **Kalibrlash** — savollarning `b` parametrini javoblar matritsasidan
     JMLE (Joint Maximum Likelihood Estimation) usuli bilan baholash.
  2. **Qobiliyatni baholash** — har bir ishtirokchi uchun `theta` ni
     Newton-Raphson usulidagi MLE orqali topish.

Modul faqat NumPy ga tayanadi va Django dan mustaqil — uni alohida
testlash mumkin.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from core import constants as C

# --------------------------------------------------------------------------
#  Yordamchi funksiyalar
# --------------------------------------------------------------------------


def probability(theta: float | np.ndarray, b: float | np.ndarray) -> np.ndarray:
    """
    Rasch modelidagi to'g'ri javob berish ehtimoli.

    Sonli barqarorlik uchun logistik funksiya to'g'ridan-to'g'ri
    `exp` orqali emas, balki `tanh` ga teng kuchli ko'rinishda hisoblanadi.
    """
    z = np.asarray(theta, dtype=float) - np.asarray(b, dtype=float)
    # 1 / (1 + exp(-z)) ning barqaror ko'rinishi
    return 0.5 * (1.0 + np.tanh(z / 2.0))


def information(theta: float | np.ndarray, b: float | np.ndarray) -> np.ndarray:
    """Savol informatsiyasi: I = P * (1 - P)."""
    p = probability(theta, b)
    return p * (1.0 - p)


def _clip_theta(value: float) -> float:
    """theta ni ruxsat etilgan oraliqqa keltiradi."""
    return float(np.clip(value, C.THETA_MIN, C.THETA_MAX))


def _clip_difficulty(value: float) -> float:
    """Qiyinlikni ruxsat etilgan oraliqqa keltiradi."""
    return float(np.clip(value, C.DIFFICULTY_MIN, C.DIFFICULTY_MAX))


# --------------------------------------------------------------------------
#  Natija konteynerlari
# --------------------------------------------------------------------------


@dataclass
class ThetaEstimate:
    """Bitta ishtirokchining qobiliyat bahosi."""

    theta: float
    standard_error: float
    raw_score: float
    max_score: float
    iterations: int = 0
    extreme: bool = False  # to'liq to'g'ri yoki to'liq noto'g'ri natija

    @property
    def percent(self) -> float:
        if self.max_score <= 0:
            return 0.0
        return round(self.raw_score / self.max_score * 100.0, 2)


@dataclass
class CalibrationResult:
    """Savollarni kalibrlash natijasi."""

    difficulties: np.ndarray
    item_p_values: np.ndarray
    item_point_biserial: np.ndarray
    iterations: int = 0
    converged: bool = True
    excluded_items: list[int] = field(default_factory=list)

    def as_list(self) -> list[float]:
        return [float(x) for x in self.difficulties]


# --------------------------------------------------------------------------
#  1. Boshlang'ich yaqinlashish (PROX)
# --------------------------------------------------------------------------


def prox_difficulties(matrix: np.ndarray) -> np.ndarray:
    """
    PROX usuli bilan savol qiyinliklarining boshlang'ich bahosi.

    b_i = ln((1 - p_i) / p_i), bu yerda p_i — i-savolga to'g'ri javob ulushi.
    Natija o'rtachasi 0 ga keltiriladi (Rasch modelidagi standart shkalalash).
    """
    n_persons, n_items = matrix.shape
    if n_persons == 0 or n_items == 0:
        return np.zeros(n_items, dtype=float)

    correct = matrix.sum(axis=0).astype(float)
    # Ekstremal savollar uchun tuzatma (0 va 100% dan qochish)
    adjusted = np.clip(correct, 0.3, n_persons - 0.3)
    p = adjusted / n_persons
    b = np.log((1.0 - p) / p)
    b = b - b.mean()
    return np.clip(b, C.DIFFICULTY_MIN, C.DIFFICULTY_MAX)


def prox_thetas(matrix: np.ndarray) -> np.ndarray:
    """Ishtirokchilar qobiliyatining boshlang'ich bahosi."""
    n_persons, n_items = matrix.shape
    if n_persons == 0 or n_items == 0:
        return np.zeros(n_persons, dtype=float)

    scores = matrix.sum(axis=1).astype(float)
    adjusted = np.clip(scores, C.EXTREME_SCORE_ADJUSTMENT, n_items - C.EXTREME_SCORE_ADJUSTMENT)
    p = adjusted / n_items
    theta = np.log(p / (1.0 - p))
    return np.clip(theta, C.THETA_MIN, C.THETA_MAX)


# --------------------------------------------------------------------------
#  2. theta ni MLE orqali baholash
# --------------------------------------------------------------------------


def estimate_theta(
    responses: np.ndarray | list[float],
    difficulties: np.ndarray | list[float],
    *,
    initial: float | None = None,
    max_iter: int = C.MLE_MAX_ITER,
    tolerance: float = C.MLE_TOLERANCE,
) -> ThetaEstimate:
    """
    Bitta ishtirokchining `theta` qiymatini Newton-Raphson MLE bilan topadi.

    Tenglama:  r - sum(P_i(theta)) = 0
    Yangilash: theta <- theta + (r - sum P) / sum(P * (1 - P))

    To'liq to'g'ri (r = L) yoki to'liq noto'g'ri (r = 0) natijalarda MLE
    cheksizlikka intiladi, shuning uchun Wright & Stone tavsiya qilgan
    0.3 ballik tuzatma qo'llaniladi.
    """
    x = np.asarray(responses, dtype=float).ravel()
    b = np.asarray(difficulties, dtype=float).ravel()

    if x.size == 0 or b.size == 0:
        return ThetaEstimate(0.0, float("inf"), 0.0, 0.0, 0, True)
    if x.size != b.size:
        size = min(x.size, b.size)
        x, b = x[:size], b[:size]

    n_items = float(b.size)
    raw_score = float(np.nansum(x))

    # Ekstremal natijalar uchun tuzatilgan ball
    extreme = raw_score <= 0.0 or raw_score >= n_items
    target = raw_score
    if extreme:
        target = float(
            np.clip(raw_score, C.EXTREME_SCORE_ADJUSTMENT, n_items - C.EXTREME_SCORE_ADJUSTMENT)
        )

    theta = float(initial) if initial is not None else _initial_theta(target, n_items)

    iterations = 0
    for iterations in range(1, max_iter + 1):
        p = probability(theta, b)
        expected = float(p.sum())
        info = float((p * (1.0 - p)).sum())
        if info < 1e-9:
            break
        step = (target - expected) / info
        # Juda katta qadamlarni cheklaymiz (barqarorlik uchun)
        step = float(np.clip(step, -1.0, 1.0))
        theta += step
        theta = _clip_theta(theta)
        if abs(step) < tolerance:
            break

    info_total = float((probability(theta, b) * (1.0 - probability(theta, b))).sum())
    se = float(1.0 / np.sqrt(info_total)) if info_total > 1e-9 else float("inf")

    return ThetaEstimate(
        theta=_clip_theta(theta),
        standard_error=se,
        raw_score=raw_score,
        max_score=n_items,
        iterations=iterations,
        extreme=extreme,
    )


def theta_for_raw_score(
    raw_score: float,
    difficulties: np.ndarray | list[float],
    **kwargs,
) -> float:
    """
    Berilgan **xom ball** uchun `theta` qiymati.

    Rasch modelida xom ball — yetarli statistika: bir xil ballga ega
    barcha javob naqshlari bir xil `theta` beradi. Shuning uchun bu yerda
    yig'indisi `raw_score` ga teng bo'lgan sun'iy javob vektori yetarli.

    Ball shkalasini daraja chegarasiga moslashtirishda ishlatiladi
    (`apps.rasch.services.anchor_theta_min`).
    """
    b = np.asarray(difficulties, dtype=float).ravel()
    if b.size == 0:
        return 0.0
    responses = np.full(b.size, float(raw_score) / float(b.size), dtype=float)
    return estimate_theta(responses, b, **kwargs).theta


def _initial_theta(score: float, n_items: float) -> float:
    """Boshlang'ich theta: logit(p)."""
    p = float(np.clip(score / max(n_items, 1.0), 0.01, 0.99))
    return _clip_theta(float(np.log(p / (1.0 - p))))


def estimate_thetas(
    matrix: np.ndarray,
    difficulties: np.ndarray | list[float],
    **kwargs,
) -> list[ThetaEstimate]:
    """Barcha ishtirokchilar uchun `theta` ni baholaydi."""
    matrix = np.asarray(matrix, dtype=float)
    if matrix.ndim == 1:
        matrix = matrix.reshape(1, -1)
    return [estimate_theta(row, difficulties, **kwargs) for row in matrix]


# --------------------------------------------------------------------------
#  3. Savollarni kalibrlash (JMLE)
# --------------------------------------------------------------------------


def calibrate(
    matrix: np.ndarray,
    *,
    anchors: dict[int, float] | None = None,
    max_iter: int = 50,
    tolerance: float = 1e-4,
) -> CalibrationResult:
    """
    Javoblar matritsasidan savol qiyinliklarini JMLE usulida baholaydi.

    Parametrlar
    -----------
    matrix : (n_persons, n_items) 0/1 qiymatli massiv.
    anchors : {item_index: difficulty} — qiyinligi qo'lda kiritilgan
              (o'zgartirilmaydigan) savollar.

    Qaytaradi
    ---------
    `CalibrationResult` — qiyinliklar va savol statistikasi.
    """
    matrix = np.asarray(matrix, dtype=float)
    if matrix.ndim == 1:
        matrix = matrix.reshape(1, -1)
    n_persons, n_items = matrix.shape
    anchors = anchors or {}

    if n_items == 0:
        return CalibrationResult(np.zeros(0), np.zeros(0), np.zeros(0), 0, True, [])

    p_values = matrix.mean(axis=0) if n_persons else np.zeros(n_items)
    point_biserial = _point_biserial(matrix)

    # Ishtirokchilar juda kam bo'lsa — faqat PROX bahosi.
    if n_persons < 3:
        b = prox_difficulties(matrix)
        for idx, value in anchors.items():
            if 0 <= idx < n_items:
                b[idx] = _clip_difficulty(value)
        return CalibrationResult(b, p_values, point_biserial, 0, False, [])

    # Ekstremal savollar (hamma to'g'ri yoki hamma xato) JMLE da chetlab o'tiladi.
    item_scores = matrix.sum(axis=0)
    excluded = [
        i for i in range(n_items)
        if item_scores[i] <= 0 or item_scores[i] >= n_persons
    ]
    estimable = np.array([i for i in range(n_items) if i not in excluded], dtype=int)

    b = prox_difficulties(matrix)
    for idx, value in anchors.items():
        if 0 <= idx < n_items:
            b[idx] = _clip_difficulty(value)
    theta = prox_thetas(matrix)

    person_scores = matrix.sum(axis=1)
    converged = False
    iteration = 0

    for iteration in range(1, max_iter + 1):
        # --- 3.1. Ishtirokchilarni yangilash ---
        p = probability(theta[:, None], b[None, :])
        expected = p.sum(axis=1)
        info = (p * (1.0 - p)).sum(axis=1)
        target = np.clip(
            person_scores,
            C.EXTREME_SCORE_ADJUSTMENT,
            n_items - C.EXTREME_SCORE_ADJUSTMENT,
        )
        with np.errstate(divide="ignore", invalid="ignore"):
            delta_theta = np.where(info > 1e-9, (target - expected) / info, 0.0)
        delta_theta = np.clip(delta_theta, -1.0, 1.0)
        theta = np.clip(theta + delta_theta, C.THETA_MIN, C.THETA_MAX)

        # --- 3.2. Savollarni yangilash ---
        p = probability(theta[:, None], b[None, :])
        expected_i = p.sum(axis=0)
        info_i = (p * (1.0 - p)).sum(axis=0)
        delta_b = np.zeros(n_items)
        if estimable.size:
            with np.errstate(divide="ignore", invalid="ignore"):
                raw_delta = np.where(
                    info_i[estimable] > 1e-9,
                    (expected_i[estimable] - item_scores[estimable]) / info_i[estimable],
                    0.0,
                )
            delta_b[estimable] = np.clip(raw_delta, -1.0, 1.0)

        # Anchor (qulflangan) savollar o'zgarmaydi
        for idx in anchors:
            if 0 <= idx < n_items:
                delta_b[idx] = 0.0

        b = np.clip(b + delta_b, C.DIFFICULTY_MIN, C.DIFFICULTY_MAX)

        # --- 3.3. Shkalani markazlashtirish (anchor bo'lmasa) ---
        if not anchors and estimable.size:
            b[estimable] -= b[estimable].mean()

        max_change = float(np.max(np.abs(delta_b))) if n_items else 0.0
        max_change = max(max_change, float(np.max(np.abs(delta_theta))) if n_persons else 0.0)
        if max_change < tolerance:
            converged = True
            break

    # Ekstremal savollarga chegaraviy qiymat beramiz
    for i in excluded:
        if i in anchors:
            continue
        if item_scores[i] <= 0:  # hech kim to'g'ri javob bermagan -> juda qiyin
            b[i] = _clip_difficulty(float(b[estimable].max()) + 1.0 if estimable.size else 3.0)
        else:  # hamma to'g'ri javob bergan -> juda oson
            b[i] = _clip_difficulty(float(b[estimable].min()) - 1.0 if estimable.size else -3.0)

    return CalibrationResult(
        difficulties=b,
        item_p_values=p_values,
        item_point_biserial=point_biserial,
        iterations=iteration,
        converged=converged,
        excluded_items=excluded,
    )


def _point_biserial(matrix: np.ndarray) -> np.ndarray:
    """
    Har bir savol uchun nuqtaviy-biserial korrelyatsiya.

    Savolning umumiy ball bilan bog'liqligini ko'rsatadi — sifat nazorati
    uchun muhim ko'rsatkich (past yoki manfiy qiymat = muammoli savol).
    """
    n_persons, n_items = matrix.shape
    result = np.zeros(n_items)
    if n_persons < 2:
        return result
    total = matrix.sum(axis=1)
    total_std = total.std()
    if total_std < 1e-9:
        return result
    for i in range(n_items):
        item = matrix[:, i]
        if item.std() < 1e-9:
            result[i] = 0.0
            continue
        rest = total - item  # o'z-o'zini hisobga olmagan korrelyatsiya
        if rest.std() < 1e-9:
            result[i] = 0.0
            continue
        result[i] = float(np.corrcoef(item, rest)[0, 1])
    return np.nan_to_num(result)


# --------------------------------------------------------------------------
#  4. Ishonchlilik ko'rsatkichlari
# --------------------------------------------------------------------------


def kr20(matrix: np.ndarray) -> float:
    """Kuder-Richardson 20 ishonchlilik koeffitsiyenti."""
    matrix = np.asarray(matrix, dtype=float)
    n_persons, n_items = matrix.shape
    if n_persons < 2 or n_items < 2:
        return 0.0
    p = matrix.mean(axis=0)
    q = 1.0 - p
    total_var = matrix.sum(axis=1).var(ddof=1)
    if total_var < 1e-9:
        return 0.0
    value = (n_items / (n_items - 1.0)) * (1.0 - float((p * q).sum()) / float(total_var))
    return float(np.clip(value, 0.0, 1.0))


def person_separation_reliability(
    thetas: list[float] | np.ndarray,
    standard_errors: list[float] | np.ndarray,
) -> float:
    """
    Rasch modelidagi ishtirokchilarni ajratish ishonchliligi.

        R = (SD^2 - MSE) / SD^2
    """
    theta_array = np.asarray(list(thetas), dtype=float)
    se_array = np.asarray(list(standard_errors), dtype=float)
    finite = np.isfinite(theta_array) & np.isfinite(se_array)
    theta_array, se_array = theta_array[finite], se_array[finite]
    if theta_array.size < 2:
        return 0.0
    observed_var = float(theta_array.var(ddof=1))
    mean_square_error = float((se_array ** 2).mean())
    if observed_var < 1e-9:
        return 0.0
    value = (observed_var - mean_square_error) / observed_var
    return float(np.clip(value, 0.0, 1.0))


__all__ = [
    "probability",
    "information",
    "ThetaEstimate",
    "CalibrationResult",
    "prox_difficulties",
    "prox_thetas",
    "estimate_theta",
    "theta_for_raw_score",
    "estimate_thetas",
    "calibrate",
    "kr20",
    "person_separation_reliability",
]
