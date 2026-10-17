import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Enum,
    Uuid,
    Boolean,
)
from sqlalchemy.orm import relationship
from app.infrastructure.database.session import Base
import enum


class TipoCodigoEnum(str, enum.Enum):
    REFERENCIA = "REFERENCIA"
    ENTREGA_ALUMNO = "ENTREGA_ALUMNO"


class DictamenEnum(str, enum.Enum):
    SIN_ALERTAS = "SIN_ALERTAS"
    REVISION_ESTILOMETRICA = "REVISION_ESTILOMETRICA"
    REVISION_SEMANTICA = "REVISION_SEMANTICA"
    DISCREPANCIA_DUAL = "DISCREPANCIA_DUAL"
    # SDD-4 (spec AS4.2): a channel could not be evaluated / the problem has no references.
    NO_EVALUABLE = "NO_EVALUABLE"
    SIN_REFERENCIA = "SIN_REFERENCIA"
    # Compatibilidad retroactiva
    INTEGRO = "SIN_ALERTAS"
    SOSPECHA_IA = "REVISION_ESTILOMETRICA"
    PLAGIO_PROBABLE = "REVISION_SEMANTICA"


class DecisionDocenteEnum(str, enum.Enum):
    PENDIENTE = "PENDIENTE"
    APROBADO = "APROBADO"
    RECHAZADO = "RECHAZADO"
    EN_DUDA = "EN_DUDA"


class EstadoAnalisisEnum(str, enum.Enum):
    PENDIENTE = "PENDIENTE"
    PROCESANDO = "PROCESANDO"
    COMPLETADO = "COMPLETADO"
    ERROR = "ERROR"


class Docente(Base):
    __tablename__ = "docentes"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    nombre = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    problemas = relationship("Problema", back_populates="docente", cascade="all, delete-orphan")
    comentarios = relationship("ComentarioRevision", back_populates="docente", cascade="all, delete-orphan")
    grupos = relationship("Grupo", back_populates="docente", cascade="all, delete-orphan")


class Grupo(Base):
    __tablename__ = "grupos"

    id = Column(Integer, primary_key=True, index=True)
    docente_id = Column(Integer, ForeignKey("docentes.id", ondelete="CASCADE"), nullable=False, index=True)
    nombre = Column(String(150), nullable=False)
    codigo_grupo = Column(String(50), nullable=False)
    periodo = Column(String(50), nullable=False)
    descripcion = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    docente = relationship("Docente", back_populates="grupos")
    asignaciones = relationship("GrupoProblema", back_populates="grupo", cascade="all, delete-orphan")
    entregas = relationship("CodigoFuente", back_populates="grupo")


class GrupoProblema(Base):
    __tablename__ = "grupo_problemas"

    id = Column(Integer, primary_key=True, index=True)
    grupo_id = Column(Integer, ForeignKey("grupos.id", ondelete="CASCADE"), nullable=False, index=True)
    problema_id = Column(Integer, ForeignKey("problemas.id", ondelete="CASCADE"), nullable=False, index=True)
    fecha_limite = Column(DateTime(timezone=True), nullable=True)
    activo = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    grupo = relationship("Grupo", back_populates="asignaciones")
    problema = relationship("Problema")


class Problema(Base):
    __tablename__ = "problemas"

    id = Column(Integer, primary_key=True, index=True)
    docente_id = Column(Integer, ForeignKey("docentes.id", ondelete="CASCADE"), nullable=False)
    titulo = Column(String(255), nullable=False)
    enunciado = Column(Text, nullable=False)
    lenguaje = Column(String(50), default="c", nullable=False)  # "c" o "cpp"
    catalogo_id = Column(String(255), nullable=True, index=True)  # id del programa del catálogo ESCOM
    fecha_creacion = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    docente = relationship("Docente", back_populates="problemas")
    codigos = relationship("CodigoFuente", back_populates="problema", cascade="all, delete-orphan")


class LoteAnalisis(Base):
    __tablename__ = "lotes_analisis"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    problema_id = Column(Integer, ForeignKey("problemas.id", ondelete="CASCADE"), nullable=False, index=True)
    docente_id = Column(Integer, ForeignKey("docentes.id", ondelete="CASCADE"), nullable=False, index=True)
    grupo_id = Column(Integer, ForeignKey("grupos.id", ondelete="SET NULL"), nullable=True, index=True)
    total_archivos = Column(Integer, default=0, nullable=False)
    procesados = Column(Integer, default=0, nullable=False)
    errores = Column(Integer, default=0, nullable=False)
    estado = Column(String(50), default="PENDIENTE", nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    problema = relationship("Problema")
    docente = relationship("Docente")
    grupo = relationship("Grupo")
    reportes = relationship("ReporteAnalisis", back_populates="lote")


class CodigoFuente(Base):
    __tablename__ = "codigos_fuente"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    problema_id = Column(Integer, ForeignKey("problemas.id", ondelete="CASCADE"), nullable=False)
    grupo_id = Column(Integer, ForeignKey("grupos.id", ondelete="SET NULL"), nullable=True, index=True)
    tipo = Column(Enum(TipoCodigoEnum), nullable=False, default=TipoCodigoEnum.ENTREGA_ALUMNO)
    autor = Column(String(255), nullable=False)
    contenido = Column(Text, nullable=False)
    lenguaje = Column(String(50), default="c", nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    problema = relationship("Problema", back_populates="codigos")
    grupo = relationship("Grupo", back_populates="entregas")
    reportes_entrega = relationship(
        "ReporteAnalisis",
        foreign_keys="ReporteAnalisis.entrega_id",
        back_populates="entrega",
        cascade="all, delete-orphan",
    )
    reportes_referencia = relationship(
        "ReporteAnalisis",
        foreign_keys="ReporteAnalisis.referencia_id",
        back_populates="referencia",
    )


class ReporteAnalisis(Base):
    __tablename__ = "reportes_analisis"

    id = Column(Integer, primary_key=True, index=True)
    entrega_id = Column(Uuid(as_uuid=True), ForeignKey("codigos_fuente.id", ondelete="CASCADE"), nullable=False)
    referencia_id = Column(Uuid(as_uuid=True), ForeignKey("codigos_fuente.id", ondelete="SET NULL"), nullable=True)
    lote_id = Column(Uuid(as_uuid=True), ForeignKey("lotes_analisis.id", ondelete="SET NULL"), nullable=True, index=True)
    # Scores: NULL means "not evaluated", never 0 (spec AR1.2). `similitud_semantica` is the raw
    # Channel A Jaccard, `probabilidad_ia` the calibrated Channel B score (design D8).
    similitud_semantica = Column(Float, nullable=True)
    probabilidad_ia = Column(Float, nullable=True)
    # Deprecated (design D15): NULL for new rows; never read by the decision.
    discrepancia_score = Column(Float, nullable=True)
    # NULL while PENDIENTE / PROCESANDO / ERROR.
    dictamen = Column(Enum(DictamenEnum), nullable=True)
    # Provenance and decision inputs (spec AR1.1, MG1.1); VARCHAR states, not PG enums (D14).
    engine = Column(String(20), nullable=True)  # "real" | "stub" | "legacy"
    canal_a_metodo = Column(String(30), nullable=True)
    estado_canal_a = Column(String(30), nullable=True)
    estado_canal_b = Column(String(30), nullable=True)
    flag_a = Column(Boolean, nullable=True)
    flag_b = Column(Boolean, nullable=True)
    umbral_a = Column(Float, nullable=True)
    umbral_b = Column(Float, nullable=True)
    puntaje_calibrado_a = Column(Float, nullable=True)
    calibracion_sha_a = Column(String(64), nullable=True)
    calibracion_sha_b = Column(String(64), nullable=True)
    checkpoint_sha_b = Column(String(64), nullable=True)
    manifest_sha = Column(String(64), nullable=True)
    # GraphCodeBERT v2 zero-shot cosine: exploratory, never decides (spec AS8).
    gcb_similarity = Column(Float, nullable=True)
    gcb_estado = Column(String(20), nullable=True)
    estado = Column(Enum(EstadoAnalisisEnum), nullable=False, default=EstadoAnalisisEnum.COMPLETADO)
    decision_docente = Column(Enum(DecisionDocenteEnum), nullable=False, default=DecisionDocenteEnum.PENDIENTE, index=True)
    fecha_decision = Column(DateTime(timezone=True), nullable=True)
    notas_docente = Column(Text, nullable=True)
    error_mensaje = Column(Text, nullable=True)
    fecha_analisis = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    entrega = relationship("CodigoFuente", foreign_keys=[entrega_id], back_populates="reportes_entrega")
    referencia = relationship("CodigoFuente", foreign_keys=[referencia_id], back_populates="reportes_referencia")
    lote = relationship("LoteAnalisis", back_populates="reportes")
    indicadores = relationship("IndicadorIntegridad", back_populates="reporte", cascade="all, delete-orphan")
    comentarios = relationship("ComentarioRevision", back_populates="reporte", cascade="all, delete-orphan")


class IndicadorIntegridad(Base):
    __tablename__ = "indicadores_integridad"

    id = Column(Integer, primary_key=True, index=True)
    reporte_id = Column(Integer, ForeignKey("reportes_analisis.id", ondelete="CASCADE"), nullable=False)
    tipo_alerta = Column(String(100), nullable=False)
    descripcion = Column(Text, nullable=False)
    severidad = Column(String(50), default="MEDIA", nullable=False)
    numero_linea = Column(Integer, nullable=True)
    categoria = Column(String(50), default="GENERAL", nullable=False)

    reporte = relationship("ReporteAnalisis", back_populates="indicadores")


class ComentarioRevision(Base):
    __tablename__ = "comentarios_revision"

    id = Column(Integer, primary_key=True, index=True)
    reporte_id = Column(Integer, ForeignKey("reportes_analisis.id", ondelete="CASCADE"), nullable=False, index=True)
    docente_id = Column(Integer, ForeignKey("docentes.id", ondelete="CASCADE"), nullable=False, index=True)
    numero_linea = Column(Integer, nullable=True)
    contenido = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    reporte = relationship("ReporteAnalisis", back_populates="comentarios")
    docente = relationship("Docente", back_populates="comentarios")
