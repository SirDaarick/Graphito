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
)
from sqlalchemy.orm import relationship
from app.infrastructure.database.session import Base
import enum


class TipoCodigoEnum(str, enum.Enum):
    REFERENCIA = "REFERENCIA"
    ENTREGA_ALUMNO = "ENTREGA_ALUMNO"


class DictamenEnum(str, enum.Enum):
    INTEGRO = "INTEGRO"
    SOSPECHA_IA = "SOSPECHA_IA"
    PLAGIO_PROBABLE = "PLAGIO_PROBABLE"


class Docente(Base):
    __tablename__ = "docentes"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    nombre = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    problemas = relationship("Problema", back_populates="docente", cascade="all, delete-orphan")


class Problema(Base):
    __tablename__ = "problemas"

    id = Column(Integer, primary_key=True, index=True)
    docente_id = Column(Integer, ForeignKey("docentes.id", ondelete="CASCADE"), nullable=False)
    titulo = Column(String(255), nullable=False)
    enunciado = Column(Text, nullable=False)
    lenguaje = Column(String(50), default="c", nullable=False)  # "c" o "cpp"
    fecha_creacion = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    docente = relationship("Docente", back_populates="problemas")
    codigos = relationship("CodigoFuente", back_populates="problema", cascade="all, delete-orphan")


class CodigoFuente(Base):
    __tablename__ = "codigos_fuente"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    problema_id = Column(Integer, ForeignKey("problemas.id", ondelete="CASCADE"), nullable=False)
    tipo = Column(Enum(TipoCodigoEnum), nullable=False, default=TipoCodigoEnum.ENTREGA_ALUMNO)
    autor = Column(String(255), nullable=False)
    contenido = Column(Text, nullable=False)
    lenguaje = Column(String(50), default="c", nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    problema = relationship("Problema", back_populates="codigos")
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
    similitud_semantica = Column(Float, nullable=False, default=0.0)
    probabilidad_ia = Column(Float, nullable=False, default=0.0)
    discrepancia_score = Column(Float, nullable=False, default=0.0)
    dictamen = Column(Enum(DictamenEnum), nullable=False, default=DictamenEnum.INTEGRO)
    fecha_analisis = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    entrega = relationship("CodigoFuente", foreign_keys=[entrega_id], back_populates="reportes_entrega")
    referencia = relationship("CodigoFuente", foreign_keys=[referencia_id], back_populates="reportes_referencia")
    indicadores = relationship("IndicadorIntegridad", back_populates="reporte", cascade="all, delete-orphan")


class IndicadorIntegridad(Base):
    __tablename__ = "indicadores_integridad"

    id = Column(Integer, primary_key=True, index=True)
    reporte_id = Column(Integer, ForeignKey("reportes_analisis.id", ondelete="CASCADE"), nullable=False)
    tipo_alerta = Column(String(100), nullable=False)
    descripcion = Column(Text, nullable=False)
    severidad = Column(String(50), default="MEDIA", nullable=False)

    reporte = relationship("ReporteAnalisis", back_populates="indicadores")
