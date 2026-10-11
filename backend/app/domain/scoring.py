"""Pure scoring domain: channel results and the decision matrix (spec AS4.1, AS4.3, AS4.4).

No framework, database or model imports. The dictamen is derived only from the two channels'
states and calibrated flags; it never reads raw scores, GraphCodeBERT, Chroma or
`discrepancia_score` (AS1.4).

Channel states (design names, used in code):
- A: `OK`, `SIN_REFERENCIA` (the problem has no references), `VACIO` (empty shingle stream),
  `SIN_CALIBRACION` (development-only `ALLOW_UNCALIBRATED`).
- B: `OK`, `ABSTENCION` (CharCNN v2 `abstained=True`), `SIN_CALIBRACION`.

A channel is evaluable only in state `OK`, and only then does it carry a flag
(`calibrated >= threshold`). Persisted and API values use the spec strings via `PERSISTED_STATE`
(decision D-B), the single mapping between both vocabularies.

Precedence: a positive flag is never hidden by the other channel being non-evaluable. Without a
positive flag, `SIN_ALERTAS` needs both channels evaluated and negative, `SIN_REFERENCIA` needs A
without references and B evaluated and negative (spec AS4.1 rows 4-5 win over the design table
for A `SIN_REFERENCIA` x B not evaluable), and every other case is `NO_EVALUABLE`.
"""

from dataclasses import dataclass, field
from typing import Mapping, Optional, Tuple

OK = "OK"
A_SIN_REFERENCIA = "SIN_REFERENCIA"
A_VACIO = "VACIO"
B_ABSTENCION = "ABSTENCION"
SIN_CALIBRACION = "SIN_CALIBRACION"

A_STATES = frozenset({OK, A_SIN_REFERENCIA, A_VACIO, SIN_CALIBRACION})
B_STATES = frozenset({OK, B_ABSTENCION, SIN_CALIBRACION})

# Design state -> persisted/API string (spec AS4.1). `VACIO` has no spec name and keeps its own.
PERSISTED_STATE: Mapping[str, str] = {
    OK: "EVALUADO",
    A_SIN_REFERENCIA: "SIN_REFERENCIA",
    A_VACIO: "VACIO",
    SIN_CALIBRACION: "NO_CALIBRADO",
    B_ABSTENCION: "ABSTENIDO",
}

DISCREPANCIA_DUAL = "DISCREPANCIA_DUAL"
REVISION_SEMANTICA = "REVISION_SEMANTICA"
REVISION_ESTILOMETRICA = "REVISION_ESTILOMETRICA"
SIN_ALERTAS = "SIN_ALERTAS"
SIN_REFERENCIA = "SIN_REFERENCIA"
NO_EVALUABLE = "NO_EVALUABLE"


@dataclass(frozen=True)
class ChannelResult:
    """One channel's measurement. `flag` is a bool iff `estado == OK`, otherwise None."""

    estado: str
    raw: Optional[float]
    calibrated: Optional[float]
    flag: Optional[bool]
    threshold: Optional[float]
    threshold_key: Optional[str]
    calibration_sha256: Optional[str]

    def __post_init__(self) -> None:
        if self.estado not in PERSISTED_STATE:
            raise ValueError(f"unknown channel state {self.estado!r}")
        if self.estado == OK:
            if not isinstance(self.flag, bool) or self.calibrated is None or self.threshold is None:
                raise ValueError("an evaluated channel needs a calibrated score, a threshold and a bool flag")
        elif self.flag is not None or self.calibrated is not None:
            raise ValueError(f"a channel in state {self.estado} carries no calibrated score or flag")

    @classmethod
    def evaluated(
        cls,
        *,
        raw: Optional[float],
        calibrated: float,
        threshold: float,
        threshold_key: Optional[str],
        calibration_sha256: Optional[str],
    ) -> "ChannelResult":
        calibrated, threshold = float(calibrated), float(threshold)
        raw = None if raw is None else float(raw)
        return cls(OK, raw, calibrated, bool(calibrated >= threshold), threshold, threshold_key, calibration_sha256)

    @classmethod
    def not_evaluated(
        cls,
        estado: str,
        *,
        raw: Optional[float] = None,
        threshold: Optional[float] = None,
        threshold_key: Optional[str] = None,
        calibration_sha256: Optional[str] = None,
    ) -> "ChannelResult":
        return cls(estado, raw, None, None, threshold, threshold_key, calibration_sha256)

    @property
    def evaluable(self) -> bool:
        return self.estado == OK

    @property
    def persisted_state(self) -> str:
        return PERSISTED_STATE[self.estado]


def decide(a: ChannelResult, b: ChannelResult) -> str:
    """The dictamen from the two channels' states and flags (see the module docstring)."""
    if a.estado not in A_STATES:
        raise ValueError(f"{a.estado!r} is not a Channel A state")
    if b.estado not in B_STATES:
        raise ValueError(f"{b.estado!r} is not a Channel B state")
    flag_a, flag_b = a.flag is True, b.flag is True
    if flag_a and flag_b:
        return DISCREPANCIA_DUAL
    if flag_a:
        return REVISION_SEMANTICA
    if flag_b:
        return REVISION_ESTILOMETRICA
    if b.evaluable and a.evaluable:
        return SIN_ALERTAS
    if b.evaluable and a.estado == A_SIN_REFERENCIA:
        return SIN_REFERENCIA
    return NO_EVALUABLE


@dataclass(frozen=True)
class ScoringOutcome:
    """Everything the scoring service decides for one submission (persisted by the caller)."""

    channel_a: ChannelResult
    channel_b: ChannelResult
    dictamen: str
    reference_id: Optional[str] = None
    gcb_similarity: Optional[float] = None
    engine: Optional[str] = None
    provenance: Mapping[str, object] = field(default_factory=dict)

    @classmethod
    def build(cls, a: ChannelResult, b: ChannelResult, **extra) -> "ScoringOutcome":
        return cls(channel_a=a, channel_b=b, dictamen=decide(a, b), **extra)

    @property
    def estado_canal_a(self) -> str:
        return self.channel_a.persisted_state

    @property
    def estado_canal_b(self) -> str:
        return self.channel_b.persisted_state

    @property
    def flag_a(self) -> Optional[bool]:
        return self.channel_a.flag

    @property
    def flag_b(self) -> Optional[bool]:
        return self.channel_b.flag

    @property
    def uncalibrated(self) -> bool:
        return SIN_CALIBRACION in (self.channel_a.estado, self.channel_b.estado)

    @property
    def flagged_channels(self) -> Tuple[str, ...]:
        """Channels with a true flag; indicators are created only for these (AS4.4)."""
        return tuple(name for name, ch in (("a", self.channel_a), ("b", self.channel_b)) if ch.flag is True)
