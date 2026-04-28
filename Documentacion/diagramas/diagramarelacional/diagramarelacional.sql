// Copia esto en ChartDB.io o Dbdiagram.io

Table DOCENTE {
  id int [pk]
  nombre string
  correo string
  password_hash string
  fecha_registro datetime
}

Table PROBLEMA {
  id int [pk]
  docente_id int [ref: > DOCENTE.id]
  titulo string
  descripcion_tecnica text
  fecha_creacion datetime
}

Table CODIGO_FUENTE {
  id int [pk]
  problema_id int [ref: > PROBLEMA.id]
  autor_id string
  es_referencia boolean
  lenguaje string
  contenido_raw text
}

Table REPORTE_ANALISIS {
  id int [pk]
  entrega_id int [ref: > CODIGO_FUENTE.id]
  referencia_id int [ref: > CODIGO_FUENTE.id]
  similitud_logica float
  probabilidad_sintetica float
  similitud_global float
  fecha_generacion datetime
}

Table INDICADOR_INTEGRIDAD {
  id int [pk]
  reporte_id int [ref: > REPORTE_ANALISIS.id]
  tipo_hallazgo string
  descripcion string
}