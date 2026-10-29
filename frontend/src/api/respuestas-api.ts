/**
 * Tipos de RESPUESTA de la API, generados desde las formas observadas.
 *
 * GENERADO AUTOMÁTICAMENTE con tools/generar-tipos-respuesta.mjs. No editar a mano.
 * Origen: frontend/forma-api.json, que recoge lo que el servidor responde de
 * verdad y que backend/app/scripts/verificar_contratos.py vuelve a comprobar.
 *
 * Estos tipos existen porque el backend no declara `response_model`: sin ellos,
 * la interfaz no podría leer un solo campo sin adivinar.
 */

/* ═══════════════════════ Respuestas ═══════════════════════ */

/** Respuesta de `GET /activos/{activo_id}` */
export type RespuestaActivosPoractivo_id = {
  "id": string,
  "tipo": string,
  "nombre_equipo": string | null,
  "codigo_patrimonial": string | null,
  "marca": string,
  "modelo": string | null,
  "estado": string,
  "propiedad": string | null,
  "oficina_id": string,
  "oficina_nombre": string,
  "zona_id": string,
  "zona_nombre": string,
  "conjunto_id": string | null,
  "conjunto_nombre": string | null,
  "responsable_id": string | null,
  "responsable_nombre": string | null,
  "uso_comun": boolean,
  "completitud": number,
  "faltantes": number,
  "campos_faltantes": string[],
  "opciones_avanzadas": boolean,
  "creado_en": string,
  "tamano_pantalla": string | null,
  "procesador": string | null,
  "memoria_ram": string | null,
  "almacenamiento": string | null,
  "direccion_ip": string | null,
  "direccion_mac": string | null,
  "observaciones": string | null,
  "campos": {
    "codigo_patrimonial": {
      "estado": string,
      "valor": unknown,
      "motivo": string,
      "nota": string | null,
      "esperado": boolean,
      "completo": boolean,
      "usuario_nombre": string,
      "fecha": string,
    },
    "marca": {
      "estado": string,
      "valor": string,
      "motivo": string | null,
      "nota": string | null,
      "esperado": boolean,
      "completo": boolean,
      "usuario_nombre": string | null,
      "fecha": string | null,
    },
    "modelo": {
      "estado": string,
      "valor": unknown,
      "motivo": string | null,
      "nota": string | null,
      "esperado": boolean,
      "completo": boolean,
      "usuario_nombre": string | null,
      "fecha": string | null,
    },
    "tamano_pantalla": {
      "estado": string,
      "valor": unknown,
      "motivo": string | null,
      "nota": string | null,
      "esperado": boolean,
      "completo": boolean,
      "usuario_nombre": string | null,
      "fecha": string | null,
    },
    "nombre_equipo": {
      "estado": string,
      "valor": unknown,
      "motivo": string | null,
      "nota": string | null,
      "esperado": boolean,
      "completo": boolean,
      "usuario_nombre": string | null,
      "fecha": string | null,
    },
    "procesador": {
      "estado": string,
      "valor": unknown,
      "motivo": string | null,
      "nota": string | null,
      "esperado": boolean,
      "completo": boolean,
      "usuario_nombre": string | null,
      "fecha": string | null,
    },
    "memoria_ram": {
      "estado": string,
      "valor": unknown,
      "motivo": string | null,
      "nota": string | null,
      "esperado": boolean,
      "completo": boolean,
      "usuario_nombre": string | null,
      "fecha": string | null,
    },
    "almacenamiento": {
      "estado": string,
      "valor": unknown,
      "motivo": string | null,
      "nota": string | null,
      "esperado": boolean,
      "completo": boolean,
      "usuario_nombre": string | null,
      "fecha": string | null,
    },
    "direccion_ip": {
      "estado": string,
      "valor": unknown,
      "motivo": string | null,
      "nota": string | null,
      "esperado": boolean,
      "completo": boolean,
      "usuario_nombre": string | null,
      "fecha": string | null,
    },
    "direccion_mac": {
      "estado": string,
      "valor": unknown,
      "motivo": string | null,
      "nota": string | null,
      "esperado": boolean,
      "completo": boolean,
      "usuario_nombre": string | null,
      "fecha": string | null,
    },
    "propiedad": {
      "estado": string,
      "valor": unknown,
      "motivo": string | null,
      "nota": string | null,
      "esperado": boolean,
      "completo": boolean,
      "usuario_nombre": string | null,
      "fecha": string | null,
    },
    "estado": {
      "estado": string,
      "valor": string,
      "motivo": string | null,
      "nota": string | null,
      "esperado": boolean,
      "completo": boolean,
      "usuario_nombre": string | null,
      "fecha": string | null,
    },
    "observaciones": {
      "estado": string,
      "valor": unknown,
      "motivo": string | null,
      "nota": string | null,
      "esperado": boolean,
      "completo": boolean,
      "usuario_nombre": string | null,
      "fecha": string | null,
    },
  },
  "campos_derivados": unknown[],
  "completitud_detalle": {
    "porcentaje": number,
    "completos": number,
    "esperados": number,
    "faltantes": number,
  },
  "historial_responsables": unknown[],
  "historial_componentes": unknown[],
  "tickets": unknown[],
  "creado_por": string,
  "actualizado_en": string,
  "version": number,
  "alertas": unknown[],
  "prediccion": {
    "probabilidad": number,
    "nivel": string,
    "horizonte_dias": number,
    "confianza": number,
    "factores": unknown[],
    "suficiente_datos": boolean,
    "muestras": number,
    "minimo_requerido": number,
    "actualizado_en": string,
    "tickets_historia": number,
    "dias_activo": number,
    "garantia_vigente": unknown,
    "metodo": string,
    "aviso": string,
  },
  "campana_estado": string,
}

/** Respuesta de `GET /analitica/equipos-prediccion` */
export type RespuestaAnaliticaEquiposPrediccion = {
  "familias": {
      "tipo": string,
      "activos": number,
      "tickets_12m": number,
      "tasa_falla": number,
      "tickets_por_equipo": number,
      "probabilidad": number,
      "nivel": string,
      "metodo": string,
      "metodo_explicacion": string,
      "horizonte_dias": number,
      "confianza": number,
      "suficiente_datos": boolean,
      "minimo_requerido": number,
      "actualizado_en": string,
    }[],
  "metodo": string,
  "explicacion": string,
  "suficiente_datos": boolean,
  "minimo_requerido": number,
  "actualizado_en": string,
}

/** Respuesta de `GET /analitica/panel` */
export type RespuestaAnaliticaPanel = {
  "kpis": {
    "periodo": {
      "desde": string,
      "hasta": string,
    },
    "tickets_analizados": number,
    "tickets_periodo_anterior": number,
    "variacion": number,
    "cerrados": number,
    "tiempo_medio_resolucion_min": number,
    "cumplimiento_sla": number,
    "satisfaccion_promedio": number,
    "precision_clasificacion": number,
    "riesgos_detectados": number,
    "casos_atendidos_anticipadamente": number,
    "tiempo_potencial_ahorrado_h": unknown,
    "confianza_media_modelo": number,
    "recomendaciones_aplicadas": number,
    "decisiones_ia": number,
    "suficiente_datos": boolean,
    "minimo_requerido": number,
  },
  "ranking_oficinas": {
    "periodo": {
      "desde": string,
      "hasta": string,
    },
    "items": {
        "id": string | null,
        "oficina": string,
        "zona": string,
        "total": number,
        "criticas": number,
        "abiertos": number,
        "vencidos": number,
        "por_equipo": number | null,
        "por_usuario": number | null,
        "equipos": number,
        "usuarios": number,
      }[],
    "normalizado": boolean,
    "maximo": number,
  },
  "ranking_zonas": {
    "items": {
        "id": string | null,
        "zona": string,
        "total": number,
        "abiertos": number,
        "criticas": number,
        "oficinas": {
            "id": string,
            "oficina": unknown,
            "total": unknown,
          }[],
        "usuarios": {
            "nombre": string,
            "oficina": unknown,
            "total": unknown,
          }[],
        "equipos": {
            "nombre": string,
            "total": unknown,
          }[],
      }[],
  },
  "mapa_calor_categoria": {
    "eje": string,
    "celdas": {
        "zona": string,
        "oficina": string,
        "valor": string,
        "total": number,
        "porcentaje": number,
        "variacion": unknown,
      }[],
    "total": number,
  },
  "mapa_calor_prioridad": {
    "eje": string,
    "celdas": {
        "zona": string,
        "oficina": string,
        "valor": string,
        "total": number,
        "porcentaje": number,
        "variacion": number | null,
      }[],
    "total": number,
  },
  "tendencia": {
    "serie": {
        "fecha": string,
        "valor": number,
      }[],
    "proyeccion": {
      "suficiente_datos": boolean,
      "muestras": number,
      "minimo_requerido": number,
      "observado": {
          "fecha": string,
          "valor": number,
        }[],
      "proyectado": {
          "fecha": string,
          "valor": number,
          "minimo": number,
          "maximo": number,
        }[],
      "tendencia": string,
      "pendiente": number,
      "actualizado_en": string,
    },
    "total_periodo": number,
  },
  "riesgo_sla_categoria": {
    "agrupar_por": string,
    "items": {
        "nombre": string,
        "total": number,
        "seguro": number,
        "atencion": number,
        "critico": number,
        "vencidos": number,
        "porcentaje_critico": number,
      }[],
  },
  "riesgo_sla_oficina": {
    "agrupar_por": string,
    "items": {
        "nombre": string,
        "total": number,
        "seguro": number,
        "atencion": number,
        "critico": number,
        "vencidos": number,
        "porcentaje_critico": number,
      }[],
  },
  "riesgo_sla_tecnico": {
    "agrupar_por": string,
    "items": {
        "nombre": string,
        "total": number,
        "seguro": number,
        "atencion": number,
        "critico": number,
        "vencidos": number,
        "porcentaje_critico": number,
      }[],
  },
  "causas": {
    "items": {
        "categoria": string,
        "equipo": string,
        "problema": string | null,
        "total": number,
        "periodo_anterior": number,
        "tendencia": unknown,
      }[],
    "suficiente_datos": boolean,
  },
  "familias_equipos": {
      "tipo": string,
      "activos": number,
      "tickets_12m": number,
      "tasa_falla": number,
      "tickets_por_equipo": number,
      "probabilidad": number,
      "nivel": string,
      "metodo": string,
      "metodo_explicacion": string,
      "horizonte_dias": number,
      "confianza": number,
      "suficiente_datos": boolean,
      "minimo_requerido": number,
      "actualizado_en": string,
    }[],
  "confianza_modelo": {
    "items": {
        "nivel": string,
        "cantidad": number,
        "porcentaje": number,
      }[],
    "confianza_media": number,
    "suficiente_datos": boolean,
    "minimo_requerido": number,
    "muestras": number,
  },
  "calidad_recomendaciones": {
    "aplicadas": number,
    "editadas": number,
    "descartadas": number,
    "total_decisiones": number,
    "tasa_aplicacion": unknown,
    "precision_confirmada": unknown,
    "retroalimentaciones": number,
    "suficiente_datos": boolean,
    "minimo_requerido": number,
  },
  "carga_tecnicos": {
    "items": {
        "tecnico_id": string | null,
        "tecnico": string,
        "asignados": number,
        "resueltos": number,
        "carga_actual": number,
        "disponibilidad": string | null,
        "incumplidos": number,
        "cumplimiento_sla": number,
        "tiempo_medio_resolucion_min": number | null,
        "reaperturas": number,
        "satisfaccion": number | null,
        "horas_laborables": number,
        "tickets_por_hora": number | null,
        "horas_por_ticket": number | null,
        "suficiente_datos": boolean,
      }[],
    "normalizado_por_horas": boolean,
  },
  "actualizado_en": string,
  "respaldo": {
    "fuente": string,
    "zona_horaria": string,
  },
  "minimos": {
    "dias_observados": number,
    "activos_para_modelo": number,
    "nota": string,
  },
}

/** Respuesta de `GET /analitica/resumen` */
export type RespuestaAnaliticaResumen = {
  "es_usuario": boolean,
  "tickets_abiertos": number,
  "tickets_sin_asignar": number,
  "tickets_sla_riesgo": number,
  "tickets_criticos": number,
  "tickets_mios": number,
  "tickets_resueltos_periodo": number,
  "tiempo_medio_resolucion_min": number,
  "cumplimiento_sla": number,
  "satisfaccion_promedio": number,
  "total_activos": number,
  "activos_con_datos_faltantes": number,
  "completitud_inventario": number,
  "usuarios_activos": number,
  "zonas": number,
  "oficinas": number,
  "equipo_disponible": number,
  "equipo_total": number,
  "tecnico_mas_carga": string,
  "top_oficinas": {
      "oficina": string,
      "total": number,
    }[],
  "top_categorias": {
      "categoria": string,
      "total": number,
    }[],
  "pendientes_calidad": {
      "activo_id": string,
      "nombre": string,
      "tipo": string,
      "codigo_patrimonial": string,
      "oficina_nombre": string,
      "oficina_id": string,
      "zona_nombre": string,
      "zona_id": string,
      "responsable_nombre": string,
      "porcentaje": number,
      "faltantes": number,
      "campos_faltantes": string[],
      "esperados": number,
    }[],
  "campana_activa": {
    "id": string,
    "verificados": number,
    "progreso": number,
    "nuevos": number,
    "modificados": number,
    "sin_cambios": number,
    "por_verificar": number,
    "discrepancias": number,
    "codigo": string,
    "nombre": string,
    "anio": number,
    "estado": string,
  },
  "ultimas_actualizaciones": string,
  "actualizado_en": string,
  "puede_ver_reportes": boolean,
  "puede_gestionar_inventario": boolean,
}

/** Respuesta de `GET /auditoria` */
export type RespuestaAuditoria = {
  "items": {
      "fecha": string,
      "accion": string,
      "accion_texto": string,
      "usuario_id": string | null,
      "usuario_nombre": string,
      "rol": string,
      "entidad": string,
      "entidad_id": unknown,
      "resultado": string,
      "resumen": string,
      "antes": unknown,
      "despues": unknown,
      "contexto": Record<string, never>,
      "ip": string | null,
      "user_agent": string | null,
      "id": string,
    }[],
  "total": number,
  "pagina": number,
  "por_pagina": number,
  "acciones": {
      "clave": string,
      "texto": string,
    }[],
  "importable": boolean,
}

/** Respuesta de `GET /ausencias?tecnico_id={tecnico_id}` */
export type RespuestaAusencias = {
  "items": {
      "tecnico_id": string,
      "tipo": string,
      "inicio": string,
      "fin": string,
      "motivo": string,
      "creado_por": string,
      "creado_en": string,
      "demo": boolean,
      "id": string,
    }[],
}

/** Respuesta de `GET /auth/preferencia-ia` */
export type RespuestaAuthPreferenciaIa = {
  "recomendaciones_ia": boolean,
  "ia_global_activa": boolean,
  "recomendaciones_globales": boolean,
  "recomendaciones_personales": boolean,
  "recomendaciones_visibles": boolean,
  "aprendizaje_activo": boolean,
  "proveedor_disponible": boolean,
  "modelo": string | null,
}

/** Respuesta de `GET /auth/sesion` */
export type RespuestaAuthSesion = {
  "id": string,
  "nombre": string,
  "email": string,
  "rol": string,
  "zona_id": string | null,
  "zona_nombre": string | null,
  "oficina_id": string | null,
  "oficina_nombre": string | null,
  "iniciales": string,
  "permisos": string[],
  "recomendaciones_ia": boolean,
  "csrf_token": string,
  "institucion": string,
  "version_password": number | null,
}

/** Respuesta de `GET /calidad-inventario` */
export type RespuestaCalidadInventario = {
  "porcentaje_global": number,
  "porcentaje_datos": number,
  "esperados_totales": number,
  "total_activos": number,
  "con_datos_completos": number,
  "faltantes_totales": number,
  "por_zona": {
      "id": string,
      "nombre": string,
      "total": number,
      "porcentaje": number,
      "porcentaje_datos": number,
      "esperados": number,
      "completos": number,
      "faltantes": number,
      "equipos_incompletos": number,
    }[],
  "por_oficina": {
      "id": string,
      "nombre": string,
      "total": number,
      "porcentaje": number,
      "porcentaje_datos": number,
      "esperados": number,
      "completos": number,
      "faltantes": number,
      "equipos_incompletos": number,
    }[],
  "por_tipo": {
      "id": string,
      "nombre": string,
      "total": number,
      "porcentaje": number,
      "porcentaje_datos": number,
      "esperados": number,
      "completos": number,
      "faltantes": number,
      "equipos_incompletos": number,
    }[],
  "por_campo": {
      "campo": string,
      "faltantes": number,
    }[],
  "pendientes": {
      "activo_id": string,
      "nombre": string,
      "tipo": string,
      "codigo_patrimonial": string,
      "oficina_nombre": string,
      "oficina_id": string,
      "zona_nombre": string,
      "zona_id": string,
      "responsable_nombre": string,
      "porcentaje": number,
      "faltantes": number,
      "campos_faltantes": string[],
      "esperados": number,
    }[],
  "pendientes_total": number,
}

/** Respuesta de `GET /calidad-inventario/esquema/Monitor` */
export type RespuestaCalidadInventarioEsquemaMonitor = {
  "esperados": string[],
  "opcionales": string[],
  "avanzadas": string[],
}

/** Respuesta de `GET /calidad-inventario/estados-campo` */
export type RespuestaCalidadInventarioEstadosCampo = {
  "estados": string[],
  "por_defecto": string,
  "no_aplica": {
    "clave": string,
    "motivos": string[],
  },
  "no_disponible": {
    "clave": string,
    "motivos": string[],
  },
  "campos": string[],
}

/** Respuesta de `GET /campanas` */
export type RespuestaCampanas = {
  "items": {
      "_id": string,
      "codigo": string,
      "nombre": string,
      "anio": number,
      "alcance": string,
      "zona_ids": string[],
      "oficina_ids": string[],
      "fecha_inicio": string,
      "fecha_fin": string,
      "responsables_nombre": unknown[],
      "notas": string,
      "generar_qr": boolean,
      "estado": string,
      "creado_en": string,
      "creado_por": string,
      "cerrado_en": string | null,
      "version_inventario": number,
      "total_items": number,
      "demo": boolean,
      "id": string,
      "verificados": number,
      "progreso": number,
      "nuevos": number,
      "nuevos_aceptados": number,
      "nuevos_descartados": number,
      "nuevos_sin_decidir": number,
      "total_registrados": number,
      "modificados": number,
      "sin_cambios": number,
      "por_verificar": number,
      "discrepancias": number,
      "cerrado_por": string,
      "nota_cierre": string,
    }[],
  "campana_activa": {
    "id": string,
    "verificados": number,
    "progreso": number,
    "nuevos": number,
    "nuevos_aceptados": number,
    "nuevos_descartados": number,
    "nuevos_sin_decidir": number,
    "total_registrados": number,
    "modificados": number,
    "sin_cambios": number,
    "por_verificar": number,
    "discrepancias": number,
    "total_items": number,
    "codigo": string,
    "nombre": string,
    "anio": number,
    "estado": string,
  },
}

/** Respuesta de `GET /campanas/{campana_id}` */
export type RespuestaCampanasPorcampana_id = {
  "codigo": string,
  "nombre": string,
  "anio": number,
  "alcance": string,
  "zona_ids": unknown[],
  "oficina_ids": unknown[],
  "fecha_inicio": string,
  "fecha_fin": string,
  "responsables": unknown[],
  "responsables_nombre": unknown[],
  "notas": string,
  "generar_qr": boolean,
  "estado": string,
  "creado_en": string,
  "creado_por": string,
  "cerrado_en": string | null,
  "version_inventario": number,
  "total_items": number,
  "demo": boolean,
  "id": string,
  "resumen": {
    "total_items": number,
    "verificados": number,
    "progreso": number,
    "nuevos": number,
    "nuevos_aceptados": number,
    "nuevos_descartados": number,
    "nuevos_sin_decidir": number,
    "total_registrados": number,
    "modificados": number,
    "sin_cambios": number,
    "por_verificar": number,
    "discrepancias": number,
  },
}

/** Respuesta de `GET /campanas/{campana_id}/items` */
export type RespuestaCampanasPorcampana_idItems = {
  "items": {
      "campana_id": string,
      "activo_id": string,
      "activo_nombre": string,
      "activo_codigo": string,
      "activo_tipo": string,
      "conjunto_nombre": string | null,
      "oficina_id": string,
      "oficina_nombre": string,
      "zona_id": string,
      "zona_nombre": string,
      "responsable_id": string | null,
      "responsable_nombre": string | null,
      "instantanea": {
        "codigo_patrimonial": string,
        "marca": string | null,
        "modelo": string | null,
        "tamano_pantalla": string | null,
        "nombre_equipo": string | null,
        "procesador": string | null,
        "memoria_ram": string | null,
        "almacenamiento": string | null,
        "direccion_ip": string | null,
        "direccion_mac": string,
        "propiedad": string | null,
        "estado": string,
        "observaciones": string,
        "responsable_id": string | null,
        "responsable_nombre": string | null,
        "oficina_id": string,
        "oficina_nombre": string,
        "zona_id": string,
        "zona_nombre": string,
        "conjunto_id": string | null,
        "conjunto_nombre": string | null,
      },
      "actual": {
        "codigo_patrimonial": string,
        "marca": string | null,
        "modelo": string | null,
        "tamano_pantalla": string | null,
        "nombre_equipo": string | null,
        "procesador": string | null,
        "memoria_ram": string | null,
        "almacenamiento": string | null,
        "direccion_ip": string | null,
        "direccion_mac": string,
        "propiedad": string | null,
        "estado": string,
        "observaciones": string,
        "responsable_id": string | null,
        "responsable_nombre": string | null,
        "oficina_id": string,
        "oficina_nombre": string,
        "zona_id": string,
        "zona_nombre": string,
        "conjunto_id": string | null,
        "conjunto_nombre": string | null,
      },
      "diferencias": unknown[],
      "estado_item": string,
      "origen": string,
      "codigo_qr": unknown,
      "observaciones": string,
      "verificado_por": unknown,
      "verificado_en": unknown,
      "demo": boolean,
      "id": string,
    }[],
  "total": number,
  "pagina": number,
  "por_pagina": number,
  "total_paginas": number,
}

/** Respuesta de `GET /campanas/{campana_id}/items?estado=verificado` */
export type RespuestaCampanasPorcampana_idItems2 = {
  "items": {
      "campana_id": string,
      "activo_id": string,
      "activo_nombre": string,
      "activo_codigo": string,
      "activo_tipo": string,
      "conjunto_nombre": string,
      "oficina_id": string,
      "oficina_nombre": string,
      "zona_id": string,
      "zona_nombre": string,
      "responsable_id": string,
      "responsable_nombre": string,
      "instantanea": {
        "codigo_patrimonial": string,
        "marca": string | null,
        "modelo": string,
        "tamano_pantalla": string,
        "nombre_equipo": string,
        "procesador": string,
        "memoria_ram": string,
        "almacenamiento": string,
        "direccion_ip": string,
        "direccion_mac": string,
        "propiedad": string,
        "estado": string,
        "observaciones": string,
        "responsable_id": string,
        "responsable_nombre": string,
        "oficina_id": string,
        "oficina_nombre": string,
        "zona_id": string,
        "zona_nombre": string,
        "conjunto_id": string,
        "conjunto_nombre": string,
      },
      "actual": {
        "codigo_patrimonial": string,
        "marca": string | null,
        "modelo": string,
        "tamano_pantalla": string,
        "nombre_equipo": string,
        "procesador": string,
        "memoria_ram": string,
        "almacenamiento": string,
        "direccion_ip": string,
        "direccion_mac": string,
        "propiedad": string,
        "estado": string,
        "observaciones": string,
        "responsable_id": string,
        "responsable_nombre": string,
        "oficina_id": string,
        "oficina_nombre": string,
        "zona_id": string,
        "zona_nombre": string,
        "conjunto_id": string,
        "conjunto_nombre": string,
      },
      "diferencias": unknown[],
      "estado_item": string,
      "origen": string,
      "codigo_qr": unknown,
      "observaciones": string,
      "verificado_por": string,
      "verificado_en": string,
      "demo": boolean,
      "id": string,
    }[],
  "total": number,
  "pagina": number,
  "por_pagina": number,
  "total_paginas": number,
}

/** Respuesta de `GET /campanas/versiones/historico` */
export type RespuestaCampanasVersionesHistorico = {
  "items": {
      "anio": number,
      "campana_id": string,
      "aplicados": number,
      "cerrado_en": string,
      "cerrado_por": string,
      "codigo_campana": string,
      "no_localizados": number,
      "nota": string,
      "resumen": {
        "total_items": number,
        "verificados": number,
        "progreso": number,
        "nuevos": number,
        "modificados": number,
        "sin_cambios": number,
        "por_verificar": number,
        "discrepancias": number,
      },
      "total_items": number,
      "demo": boolean,
      "id": string,
    }[],
}

/** Respuesta de `GET /configuracion` */
export type RespuestaConfiguracion = {
  "_id": string,
  "ia": {
    "global_activa": boolean,
    "aprendizaje_activo": boolean,
    "recomendaciones_activas": boolean,
    "valor_por_defecto": boolean,
    "confianza_minima": number,
    "proveedor": string,
    "modelo": string,
  },
  "institucion": {
    "nombre": string,
    "nombre_corto": string,
    "correo": string,
  },
  "inventario": {
    "importacion_completada": boolean,
    "plantilla_mapeo": unknown,
  },
  "negocio": {
    "zona_horaria": string,
    "horario_inicio_global": string,
    "horario_fin_global": string,
  },
  "notificaciones": {
    "email_activo": boolean,
    "correo_destino": string,
    "avisar_al_afectado": boolean,
    "avisar_al_reportante": boolean,
  },
  "sistema": {
    "version": string,
    "creado_en": string,
    "primer_arranque_completo": boolean,
    "datos_demo": boolean,
    "demo_creado_en": string,
  },
  "sla": {
    "activo": boolean,
    "pausa_fuera_de_horario": boolean,
    "reglas": {
        "prioridad": string,
        "horas_responder": number,
        "horas_resolver": number,
      }[],
    "calendario": {
      "dias_laborables": number[],
      "tramos": {
          "entrada": string,
          "salida": string,
        }[],
      "incluir_feriados": boolean,
      "feriados_extra": unknown[],
    },
  },
}

/** Respuesta de `GET /configuracion/catalogos` */
export type RespuestaConfiguracionCatalogos = {
  "catalogos": {
    "canales_notificacion": {
        "valor": string,
        "etiqueta": string,
        "activo": boolean,
        "orden": number,
      }[],
    "categorias": {
        "valor": string,
        "etiqueta": string,
        "activo": boolean,
        "orden": number,
      }[],
    "componentes_conjunto": {
        "valor": string,
        "etiqueta": string,
        "activo": boolean,
        "orden": number,
      }[],
    "estados_activo": {
        "valor": string,
        "etiqueta": string,
        "activo": boolean,
        "orden": number,
      }[],
    "motivos_no_aplica": {
        "valor": string,
        "etiqueta": string,
        "activo": boolean,
        "orden": number,
      }[],
    "motivos_no_disponible": {
        "valor": string,
        "etiqueta": string,
        "activo": boolean,
        "orden": number,
      }[],
    "motivos_sin_dato": {
        "valor": string,
        "etiqueta": string,
        "activo": boolean,
        "orden": number,
      }[],
    "propiedades": {
        "valor": string,
        "etiqueta": string,
        "activo": boolean,
        "orden": number,
      }[],
    "sinonimos_dispositivo": {
        "valor": string,
        "etiqueta": string,
        "activo": boolean,
        "orden": number,
      }[],
    "tipos_ausencia": {
        "valor": string,
        "etiqueta": string,
        "activo": boolean,
        "orden": number,
      }[],
    "tipos_dispositivo": {
        "valor": string,
        "etiqueta": string,
        "activo": boolean,
        "orden": number,
      }[],
  },
  "esquemas": {
      "tipo": string,
      "esperados": string[],
      "opcionales": string[],
      "avanzadas": string[],
    }[],
}

/** Respuesta de `GET /configuracion/estado-ia` */
export type RespuestaConfiguracionEstadoIa = {
  "proveedor": string,
  "modelo": string | null,
  "base_url": unknown,
  "disponible": boolean,
  "motivo": string,
  "funcionalidad": string,
}

/** Respuesta de `GET /configuracion/feriados` */
export type RespuestaConfiguracionFeriados = {
  "items": {
      "fecha": string,
      "nombre": string,
      "tipo": string,
      "creado_en": string,
      "demo": boolean,
      "id": string,
    }[],
}

/** Respuesta de `GET /conjuntos` */
export type RespuestaConjuntos = {
  "items": {
      "id": string,
      "nombre": string,
      "nombre_normalizado": string,
      "numero": number,
      "oficina_id": string,
      "oficina_nombre": string,
      "zona_id": string,
      "zona_nombre": string,
      "responsable_id": string | null,
      "responsable_nombre": string | null,
      "uso_comun": boolean,
      "estado": string,
      "notas": string,
      "activo": boolean,
      "creado_en": string,
      "creado_por": string,
      "actualizado_en": string,
      "total_activos": number,
      "activos_operativos": number,
      "opciones_avanzadas": number,
      "completitud": number,
      "pendientes": number,
    }[],
}

/** Respuesta de `GET /conjuntos/siguiente-nombre?oficina_id={oficina_id}` */
export type RespuestaConjuntosSiguienteNombre = {
  "nombre": string,
}

/** Respuesta de `GET /equipo-ti/{tecnico_id}` */
export type RespuestaEquipoTiPortecnico_id = {
  "id": string,
  "nombre": string,
  "email": string,
  "telefono": string | null,
  "anexo": string | null,
  "cargo": string,
  "rol": string,
  "activo": boolean,
  "zona_id": string,
  "zona_nombre": string,
  "oficina_id": string,
  "oficina_nombre": string,
  "iniciales": string,
  "ultimo_acceso": unknown,
  "creado_en": string,
  "recomendaciones_ia": boolean,
  "perfil": {
    "especialidades": string[],
    "categorias": string[],
    "zonas_pref": unknown[],
    "capacidad_diaria": number,
    "notas": string | null,
    "activo": boolean,
  },
  "horario": {
    "dias": {
      "0": {
        "tramos": {
            "entrada": string,
            "salida": string,
          }[],
        "libre": boolean,
      },
      "1": {
        "tramos": {
            "entrada": string,
            "salida": string,
          }[],
        "libre": boolean,
      },
      "2": {
        "tramos": {
            "entrada": string,
            "salida": string,
          }[],
        "libre": boolean,
      },
      "3": {
        "tramos": {
            "entrada": string,
            "salida": string,
          }[],
        "libre": boolean,
      },
      "4": {
        "tramos": {
            "entrada": string,
            "salida": string,
          }[],
        "libre": boolean,
      },
      "5": {
        "tramos": {
            "entrada": string,
            "salida": string,
          }[],
        "libre": boolean,
      },
      "6": {
        "tramos": {
            "entrada": string,
            "salida": string,
          }[],
        "libre": boolean,
      },
    },
  },
  "disponibilidad": {
    "tecnico_id": string,
    "tecnico_nombre": string,
    "estado": string,
    "etiqueta": string,
    "ticket_actual_id": string,
    "ticket_actual_codigo": string,
    "ticket_desde": string,
    "ticket_zona": string,
    "ticket_oficina": string,
    "carga_asignados": number,
    "carga_espera": number,
    "capacidad_diaria": number,
    "porcentaje_carga": number,
    "sla_mas_critico_min": number,
    "horario_hoy": unknown[],
    "ausencias": {
        "tecnico_id": string,
        "tipo": string,
        "inicio": string,
        "fin": string,
        "motivo": string,
        "creado_por": string,
        "creado_en": string,
        "demo": boolean,
        "id": string,
      }[],
    "dia_libre": boolean,
    "fuera_de_horario": boolean,
    "metricas": {
      "tickets_atendidos": number,
      "tickets_asignados_periodo": number,
      "tiempo_medio_resolucion_min": number,
      "cumplimiento_sla": number,
      "reaperturas": number,
      "satisfaccion": number,
      "horas_laborables_periodo": number,
      "horas_laborables_por_ticket": number,
      "insuficientes_datos": boolean,
    },
    "pendientes_sin_responder": number,
  },
  "metricas": {
    "tickets_atendidos": number,
    "tickets_asignados_periodo": number,
    "tiempo_medio_resolucion_min": number,
    "cumplimiento_sla": number,
    "reaperturas": number,
    "satisfaccion": number,
    "horas_laborables_periodo": number,
    "horas_laborables_por_ticket": number,
    "insuficientes_datos": boolean,
  },
  "ausencias": {
      "tecnico_id": string,
      "tipo": string,
      "inicio": string,
      "fin": string,
      "motivo": string,
      "creado_por": string,
      "creado_en": string,
      "demo": boolean,
      "id": string,
    }[],
}

/** Respuesta de `GET /equipo-ti/calendario` */
export type RespuestaEquipoTiCalendario = {
  "desde": string,
  "hasta": string,
  "items": {
      "fecha": string,
      "tecnico_id": string,
      "tecnico_nombre": string,
      "tramos": {
          "entrada": string,
          "salida": string,
        }[],
      "libre": boolean,
      "feriado": boolean,
      "ausencia": unknown,
    }[],
  "dias_semana": string[],
}

/** Respuesta de `GET /equipo-ti/mi-horario/permiso` */
export type RespuestaEquipoTiMiHorarioPermiso = {
  "puedo": boolean,
  "explicacion": string,
}

/** Respuesta de `GET /equipo-ti/panel` */
export type RespuestaEquipoTiPanel = {
  "items": {
      "tecnico_id": string,
      "tecnico_nombre": string,
      "estado": string,
      "etiqueta": string,
      "ticket_actual_id": string | null,
      "ticket_actual_codigo": string | null,
      "ticket_desde": string | null,
      "ticket_zona": string | null,
      "ticket_oficina": string | null,
      "carga_asignados": number,
      "carga_espera": number,
      "capacidad_diaria": number,
      "porcentaje_carga": number,
      "sla_mas_critico_min": number | null,
      "horario_hoy": unknown[],
      "ausencias": unknown[],
      "dia_libre": boolean,
      "fuera_de_horario": boolean,
      "metricas": {
        "tickets_atendidos": number,
        "tickets_asignados_periodo": number,
        "tiempo_medio_resolucion_min": number | null,
        "cumplimiento_sla": number | null,
        "reaperturas": number,
        "satisfaccion": number | null,
        "horas_laborables_periodo": number,
        "horas_laborables_por_ticket": number | null,
        "insuficientes_datos": boolean,
      },
      "pendientes_sin_responder": number,
    }[],
  "actualizado_en": string,
}

/** Respuesta de `GET /equipo-ti/tecnicos` */
export type RespuestaEquipoTiTecnicos = {
  "items": {
      "id": string,
      "nombre": string,
      "rol": string,
    }[],
}

/** Respuesta de `GET /equipos/buscar?texto=a` */
export type RespuestaEquiposBuscar = {
  "items": {
      "id": string,
      "tipo": string,
      "nombre": string,
      "codigo_patrimonial": string,
      "oficina_nombre": string,
      "responsable_nombre": string | null,
      "estado": string,
    }[],
}

/** Respuesta de `GET /equipos/catalogos` */
export type RespuestaEquiposCatalogos = {
  "canales_notificacion": {
      "valor": string,
      "etiqueta": string,
      "activo": boolean,
      "orden": number,
    }[],
  "categorias": {
      "valor": string,
      "etiqueta": string,
      "activo": boolean,
      "orden": number,
    }[],
  "componentes_conjunto": {
      "valor": string,
      "etiqueta": string,
      "activo": boolean,
      "orden": number,
    }[],
  "estados_activo": {
      "valor": string,
      "etiqueta": string,
      "activo": boolean,
      "orden": number,
    }[],
  "motivos_no_aplica": {
      "valor": string,
      "etiqueta": string,
      "activo": boolean,
      "orden": number,
    }[],
  "motivos_no_disponible": {
      "valor": string,
      "etiqueta": string,
      "activo": boolean,
      "orden": number,
    }[],
  "motivos_sin_dato": {
      "valor": string,
      "etiqueta": string,
      "activo": boolean,
      "orden": number,
    }[],
  "propiedades": {
      "valor": string,
      "etiqueta": string,
      "activo": boolean,
      "orden": number,
    }[],
  "sinonimos_dispositivo": {
      "valor": string,
      "etiqueta": string,
      "activo": boolean,
      "orden": number,
    }[],
  "tipos_ausencia": {
      "valor": string,
      "etiqueta": string,
      "activo": boolean,
      "orden": number,
    }[],
  "tipos_dispositivo": {
      "valor": string,
      "etiqueta": string,
      "activo": boolean,
      "orden": number,
    }[],
}

/** Respuesta de `GET /equipos/por-codigo?codigo=INEXISTENTE` */
export type RespuestaEquiposPorCodigo = {
  "items": {
      "id": string,
      "tipo": string,
      "nombre": string,
      "codigo_patrimonial": string,
      "marca": string | null,
      "modelo": string | null,
      "oficina_nombre": string,
      "conjunto_nombre": string,
      "responsable_id": string | null,
      "responsable_nombre": string | null,
    }[],
}

/** Respuesta de `GET /equipos/sugerencias?campo=marca` */
export type RespuestaEquiposSugerencias = {
  "campo": string,
  "tipo": string | null,
  "marca": string | null,
  "valores": {
      "valor": string,
      "frecuencia": number,
      "marca": string,
      "frecuencia_marca": number,
      "ejemplo_completo": unknown,
    }[],
}

/** Respuesta de `GET /equipos/sugerencias?campo=marca&marca=HP` */
export type RespuestaEquiposSugerencias2 = {
  "campo": string,
  "tipo": string | null,
  "marca": string,
  "valores": {
      "valor": string,
      "frecuencia": number,
      "marca": string,
      "frecuencia_marca": number,
      "ejemplo_completo": unknown,
    }[],
}

/** Respuesta de `GET /exportaciones` */
export type RespuestaExportaciones = {
  "items": {
      "tipo": string,
      "formato": string,
      "nombre_archivo": string,
      "estado": string,
      "usuario_id": string,
      "usuario_nombre": string,
      "tamanio": number,
      "error": string,
      "creado_en": string,
      "completado_en": string,
      "id": string,
      "descarga_url": string,
    }[],
}

/** Respuesta de `GET /ia/asistente/conversaciones` */
export type RespuestaIaAsistenteConversaciones = {
  "items": unknown[],
}

/** Respuesta de `GET /ia/asistente/preguntas` */
export type RespuestaIaAsistentePreguntas = {
  "preguntas": string[],
}

/** Respuesta de `GET /ia/sugerencias-reporte?tipo_problema=x` */
export type RespuestaIaSugerenciasReporte = {
  "disponible": boolean,
  "categoria": string | null,
  "articulos": {
      "id": string,
      "titulo": string,
      "resumen": string,
      "categoria": string,
    }[],
  "explicacion": string,
}

/** Respuesta de `GET /importacion` */
export type RespuestaImportacion = {
  "items": {
      "_id": string,
      "id": string,
      "nombre_archivo": string,
      "estado": string,
      "creado_en": string,
      "confirmado_en": string | null,
      "creados": string[],
      "actualizados": string[],
      "omitidos": number,
      "errores": unknown[],
      "total_filas": number,
      "reversible": boolean,
      "usuario_nombre": string | null,
    }[],
}

/** Respuesta de `GET /instalacion` */
export type RespuestaInstalacion = {
  "configurado": boolean,
  "hay_admin": boolean,
  "hay_zonas": boolean,
  "hay_oficinas": boolean,
  "hay_usuarios": boolean,
  "hay_tecnicos": boolean,
  "hay_inventario": boolean,
  "inventario_importado": boolean,
  "horarios_completos": boolean,
  "pasos": {
      "clave": string,
      "titulo": string,
      "hecho": boolean,
      "alternativa": string,
      "alternativa_hecha": boolean,
    }[],
  "pasos_completados": string[],
  "siguiente_paso": string,
  "institucion": string,
}

/** Respuesta de `GET /kb/articulos` */
export type RespuestaKbArticulos = {
  "items": {
      "id": string,
      "titulo": string,
      "categoria": string,
      "resumen": string,
      "etiquetas": string[],
      "pasos": string[],
      "imagenes": unknown[],
      "relacionados": string[],
      "popularidad": number,
      "visualizaciones": number,
      "valoracion_promedio": number,
      "valoraciones": number,
      "actualizado_en": string,
      "activo": boolean,
    }[],
  "total": number,
  "pagina": number,
  "por_pagina": number,
  "total_paginas": number,
}

/** Respuesta de `GET /kb/articulos/{articulo_id}` */
export type RespuestaKbArticulosPorarticulo_id = {
  "id": string,
  "titulo": string,
  "categoria": string,
  "resumen": string,
  "etiquetas": string[],
  "pasos": string[],
  "imagenes": unknown[],
  "relacionados": string[],
  "popularidad": number,
  "visualizaciones": number,
  "valoracion_promedio": number | null,
  "valoraciones": number,
  "actualizado_en": string,
  "activo": boolean,
  "cuerpo": string,
  "creado_en": string,
  "creado_por": string,
}

/** Respuesta de `GET /kb/categorias` */
export type RespuestaKbCategorias = {
  "items": string[],
}

/** Respuesta de `GET /kb/respuestas-rapidas` */
export type RespuestaKbRespuestasRapidas = {
  "items": {
      "titulo": string,
      "cuerpo": string,
      "categoria": string,
      "activo": boolean,
      "orden": number,
      "creado_en": string,
      "demo": boolean,
      "id": string,
    }[],
}

/** Respuesta de `GET /mi-perfil` */
export type RespuestaMiPerfil = {
  "id": string,
  "nombre": string,
  "email": string,
  "telefono": string | null,
  "anexo": string | null,
  "cargo": string,
  "rol": string,
  "activo": boolean,
  "zona_id": string | null,
  "zona_nombre": string | null,
  "oficina_id": string | null,
  "oficina_nombre": string | null,
  "iniciales": string,
  "ultimo_acceso": string,
  "creado_en": string,
  "recomendaciones_ia": boolean,
  "equipos_responsable": unknown[],
  "historial_responsabilidad": unknown[],
  "tickets_creados": number,
  "tickets_afectado": number,
  "tickets_activos": number,
  "horario": {
    "dias": {
      "1": {
        "tramos": {
            "entrada": string,
            "salida": string,
          }[],
        "libre": boolean,
      },
      "2": {
        "tramos": {
            "entrada": string,
            "salida": string,
          }[],
        "libre": boolean,
      },
      "3": {
        "tramos": {
            "entrada": string,
            "salida": string,
          }[],
        "libre": boolean,
      },
      "4": {
        "tramos": {
            "entrada": string,
            "salida": string,
          }[],
        "libre": boolean,
      },
      "5": {
        "tramos": {
            "entrada": string,
            "salida": string,
          }[],
        "libre": boolean,
      },
    },
  },
  "carga_actual": number,
  "especiales": unknown[],
  "permisos": {
    "equipos.crear": boolean,
    "equipos.editar": boolean,
    "equipos.eliminar": boolean,
    "equipos.importar": boolean,
    "equipos.acciones_masivas": boolean,
    "equipos.opciones_avanzadas": boolean,
    "equipos.marcar_no_aplica": boolean,
    "equipos.campanas": boolean,
    "org.editar": boolean,
    "usuarios.editar": boolean,
    "tickets.reasignar": boolean,
    "tickets.cerrar_reabrir": boolean,
    "tickets.eliminar": boolean,
    "kb.editar": boolean,
    "reportes.ver": boolean,
    "exportar": boolean,
    "analitica.ver": boolean,
    "horarios.editar_propio": boolean,
    "horarios.editar_todos": boolean,
    "vistas.compartidas": boolean,
  },
  "permisos_efectivos": string[],
}

/** Respuesta de `GET /notificaciones` */
export type RespuestaNotificaciones = {
  "items": {
      "usuario_id": string,
      "titulo": string,
      "mensaje": string,
      "tipo": string,
      "enlace": string,
      "ticket_id": string,
      "leida": boolean,
      "creado_en": string,
      "demo": boolean,
      "id": string,
    }[],
  "no_leidas": number,
}

/** Respuesta de `GET /oficinas` */
export type RespuestaOficinas = {
  "items": {
      "id": string,
      "nombre": string,
      "nombre_normalizado": string,
      "zona_id": string,
      "zona_nombre": string,
      "descripcion": string,
      "activa": boolean,
      "creado_en": string,
      "creado_por": string,
      "actualizado_en": string,
      "total_usuarios": number,
      "total_equipos": number,
      "demo": boolean,
    }[],
}

/** Respuesta de `GET /oficinas/{oficina_id}` */
export type RespuestaOficinasPoroficina_id = {
  "id": string,
  "nombre": string,
  "zona_id": string,
  "zona_nombre": string,
  "descripcion": string | null,
  "activa": boolean,
  "creado_en": string,
  "total_usuarios": number,
  "total_equipos": number,
  "tickets_abiertos": number,
  "usuarios": unknown[],
  "equipos_uso_comun": unknown[],
  "equipos_por_usuario": unknown[],
  "pendientes_calidad": unknown[],
  "completitud_inventario": number,
  "tickets_recientes": unknown[],
  "tendencia": unknown[],
  "incidencias_recurrentes": unknown[],
}

/** Respuesta de `GET /permisos/matriz` */
export type RespuestaPermisosMatriz = {
    "grupo": string,
    "etiqueta": string,
    "descripcion": string,
    "permisos": {
        "clave": string,
        "etiqueta": string,
        "descripcion": string,
      }[],
  }[]

/** Respuesta de `GET /permisos/tecnicos` */
export type RespuestaPermisosTecnicos = {
  "items": {
      "usuario_id": string,
      "nombre": string,
      "rol": string,
      "activo": boolean,
      "permisos": {
        "equipos.crear": boolean,
        "equipos.editar": boolean,
        "equipos.eliminar": boolean,
        "equipos.importar": boolean,
        "equipos.acciones_masivas": boolean,
        "equipos.opciones_avanzadas": boolean,
        "equipos.marcar_no_aplica": boolean,
        "equipos.campanas": boolean,
        "org.editar": boolean,
        "usuarios.editar": boolean,
        "tickets.reasignar": boolean,
        "tickets.cerrar_reabrir": boolean,
        "tickets.eliminar": boolean,
        "kb.editar": boolean,
        "reportes.ver": boolean,
        "exportar": boolean,
        "analitica.ver": boolean,
        "horarios.editar_propio": boolean,
        "horarios.editar_todos": boolean,
        "vistas.compartidas": boolean,
      },
    }[],
  "matriz_inicial": {
    "equipos.crear": boolean,
    "equipos.editar": boolean,
    "equipos.eliminar": boolean,
    "equipos.importar": boolean,
    "equipos.acciones_masivas": boolean,
    "equipos.opciones_avanzadas": boolean,
    "equipos.marcar_no_aplica": boolean,
    "equipos.campanas": boolean,
    "org.editar": boolean,
    "usuarios.editar": boolean,
    "tickets.reasignar": boolean,
    "tickets.cerrar_reabrir": boolean,
    "tickets.eliminar": boolean,
    "kb.editar": boolean,
    "reportes.ver": boolean,
    "exportar": boolean,
    "analitica.ver": boolean,
    "horarios.editar_propio": boolean,
    "horarios.editar_todos": boolean,
    "vistas.compartidas": boolean,
  },
}

/** Respuesta de `GET /publico/configuracion` */
export type RespuestaPublicoConfiguracion = {
  "institucion": string,
  "nombre_corto": string,
  "correo": string,
  "zona_horaria": string,
  "version": string,
}

/** Respuesta de `GET /salud` */
export type RespuestaSalud = {
  "ok": boolean,
}

/** Respuesta de `GET /tickets` */
export type RespuestaTickets = {
  "items": {
      "id": string,
      "codigo": string,
      "asunto": string,
      "descripcion": string | null,
      "estado": string,
      "prioridad": string,
      "origen": string,
      "categoria": string | null,
      "reportante_id": string,
      "reportante_nombre": string,
      "afectado_id": string,
      "afectado_nombre": string,
      "zona_id": string | null,
      "zona_nombre": string | null,
      "oficina_id": string | null,
      "oficina_nombre": string | null,
      "activo_id": string | null,
      "activo_nombre": string | null,
      // El tipo puede existir sin equipo enlazado: quien registra el caso puede
      // anotar «es un CPU» sin saber qué máquina es. Entonces `activo_id` es nulo
      // y el tipo es lo único que hay.
      "activo_tipo": string | null,
      "conjunto_id": string | null,
      "conjunto_nombre": string | null,
      "tecnico_id": string | null,
      "tecnico_nombre": string | null,
      "creado_en": string,
      "actualizado_en": string,
      "sla": {
        "activo": boolean,
        "estado": string,
        "minutos_restantes": unknown,
        "minutos_transcurridos": number,
        "modo": string,
        "minutos_responder_restantes": number | null,
        "minutos_resolver_restantes": number | null,
        "minutos_retraso": number,
        "responder_en": string,
        "resolver_en": string,
        "pausado": boolean,
        "progreso": number,
      },
      "tiempo_resolucion_min": number | null,
      "aceptacion": {
        "consta": boolean,
        "en": string | null,
        "minutos": number | null,
        "plazo_minutos": number | null,
        "cumplio": boolean | null,
        "reconstruido": boolean,
      },
      "confianza_ia": unknown,
      "mensajes_no_leidos": number,
      "satisfaccion": unknown,
      "sla_incumplido": boolean,
      "tiene_chat": boolean,
      "detectado_por_tecnico": boolean,
    }[],
  "total": number,
  "pagina": number,
  "por_pagina": number,
  "total_paginas": number,
}

/** Respuesta de `GET /tickets/{ticket_id}` */
export type RespuestaTicketsPorticket_id = {
  "id": string,
  "codigo": string,
  "asunto": string,
  "descripcion": string,
  "estado": string,
  "prioridad": string,
  "origen": string,
  "categoria": string,
  "reportante_id": string,
  "reportante_nombre": string,
  "afectado_id": string,
  "afectado_nombre": string,
  "zona_id": string,
  "zona_nombre": string,
  "oficina_id": string,
  "oficina_nombre": string,
  "activo_id": string,
  "activo_nombre": string,
  "activo_tipo": string | null,
  "conjunto_id": string,
  "conjunto_nombre": string,
  "tecnico_id": string,
  "tecnico_nombre": string,
  "creado_en": string,
  "actualizado_en": string,
  "sla": {
    "activo": boolean,
    "estado": string,
    "minutos_restantes": unknown,
    "minutos_transcurridos": number,
    "modo": string,
    "minutos_responder_restantes": number | null,
    "minutos_resolver_restantes": number | null,
    "minutos_retraso": number,
    "responder_en": string,
    "resolver_en": string,
    "pausado": boolean,
    "progreso": number,
  },
  "tiempo_resolucion_min": number,
  "aceptacion": {
    "consta": boolean,
    "en": string | null,
    "minutos": number | null,
    "plazo_minutos": number | null,
    "cumplio": boolean | null,
    "reconstruido": boolean,
  },
  "confianza_ia": unknown,
  "mensajes_no_leidos": number,
  "satisfaccion": unknown,
  "sla_incumplido": boolean,
  "tiene_chat": boolean,
  "detectado_por_tecnico": boolean,
  "conversacion_id": string,
  "resuelto_en": string,
  "cerrado_en": string,
  "nota_resolucion": string,
  "veces_reabierto": number,
  "urgencia": string,
  "tipo_problema": string,
  "notas_internas": unknown[],
  "eventos": {
      "ticket_id": string,
      "tipo": string,
      "fecha": string,
      "actor": {
        "id": string,
        "nombre": string,
        "rol": string,
      },
      "resumen": string,
      "detalle": Record<string, never>,
      "visible_usuario": boolean,
      "origen_ia": boolean,
      "demo": boolean,
      "id": string,
    }[],
  "puede_operar": boolean,
  "puede_eliminar": boolean,
  "adjuntos": unknown[],
  "afectado_equipos": {
    "por_conjunto": {
        "conjunto": string,
        "equipos": {
            "id": string,
            "tipo": string,
            "nombre_equipo": string,
            "codigo_patrimonial": string,
            "marca": string,
            "modelo": string,
            "estado": string,
            "propiedad": string,
            "oficina_id": string,
            "oficina_nombre": string,
            "zona_id": string,
            "zona_nombre": string,
            "conjunto_id": string,
            "conjunto_nombre": string,
            "responsable_id": string,
            "responsable_nombre": string,
            "uso_comun": boolean,
            "completitud": unknown,
            "faltantes": unknown,
            "campos_faltantes": unknown,
            "opciones_avanzadas": boolean,
            "creado_en": string,
          }[],
      }[],
    "uso_comun_oficina": {
        "id": string,
        "tipo": string,
        "nombre_equipo": string,
        "codigo_patrimonial": string,
        "marca": string | null,
        "modelo": string | null,
        "estado": string,
        "propiedad": string,
        "oficina_id": string,
        "oficina_nombre": string,
        "zona_id": string,
        "zona_nombre": string,
        "conjunto_id": string,
        "conjunto_nombre": string,
        "responsable_id": string,
        "responsable_nombre": string,
        "uso_comun": boolean,
        "completitud": number,
        "faltantes": number,
        "campos_faltantes": string[],
        "opciones_avanzadas": boolean,
        "creado_en": string,
      }[],
    "conjuntos": {
        "id": string,
        "nombre": string,
        "oficina_nombre": string,
        "numero": number,
      }[],
  },
}

/** Respuesta de `GET /tickets/{ticket_id}/ia` */
export type RespuestaTicketsPorticket_idIa = {
  "disponible": boolean,
  "categoria": string,
  "prioridad": string,
  "confianza": number,
  "confianza_suficiente": boolean,
  "explicacion": string,
  "resumen": string | null,
  "causa_raiz": unknown,
  "riesgo_sla": string,
  "articulos": {
      "id": string,
      "titulo": string,
      "resumen": string,
      "categoria": string,
    }[],
  "respuesta_sugerida": string | null,
  "tecnico_sugerido_id": string,
  "tecnico_sugerido_nombre": string,
  "explicacion_asignacion": string,
  "activa": boolean,
  "llm_disponible": boolean,
}

/** Respuesta de `GET /tickets/{ticket_id}/mensajes` */
export type RespuestaTicketsPorticket_idMensajes = {
  "items": {
      "ticket_id": string,
      "conversacion_id": string,
      "autor_id": string,
      "autor_nombre": string,
      "autor_rol": string,
      "cuerpo": string,
      "adjuntos": unknown[],
      "leido_por_tecnico": boolean,
      "creado_en": string,
      "es_ia": boolean,
      "demo": boolean,
      "id": string,
    }[],
}

/** Respuesta de `GET /tickets/{ticket_id}/notas` */
export type RespuestaTicketsPorticket_idNotas = {
  "items": unknown[],
}

/** Respuesta de `GET /tickets/ajustes-crear` */
export type RespuestaTicketsAjustesCrear = {
  "categorias": string[],
  "tipos_equipo": string[],
  "estados": string[],
  "propiedades": string[],
  "urgencias": {
      "clave": string,
      "titulo": string,
      "texto": string,
    }[],
  "tipos_problema": {
      "clave": string,
      "titulo": string,
      "descripcion": string,
      "icono": string,
    }[],
  "zonas": unknown[],
  "origenes": string[],
  "prioridades": string[],
  "estados_ticket": string[],
}

/** Respuesta de `GET /tickets/resumen` */
export type RespuestaTicketsResumen = {
  "es_usuario": boolean,
  "abiertos": number,
  "sin_asignar": number,
  "sla_riesgo": number,
  "criticos": number,
  "mios": number,
  "cerrados": number,
  "puede_ver_reportes": boolean,
}

/** Respuesta de `GET /usuarios` */
export type RespuestaUsuarios = {
  "items": {
      "id": string,
      "nombre": string,
      "email": string,
      "telefono": string,
      "anexo": string,
      "cargo": string | null,
      "rol": string,
      "activo": boolean,
      "zona_id": string,
      "zona_nombre": string,
      "oficina_id": string,
      "oficina_nombre": string,
      "iniciales": string,
      "ultimo_acceso": string | null,
      "creado_en": string,
      "recomendaciones_ia": boolean,
    }[],
  "total": number,
  "pagina": number,
  "por_pagina": number,
  "total_paginas": number,
}

/** Respuesta de `GET /usuarios/{usuario_id}` */
export type RespuestaUsuariosPorusuario_id = {
  "id": string,
  "nombre": string,
  "email": string,
  "telefono": string | null,
  "anexo": string | null,
  "cargo": string | null,
  "rol": string,
  "activo": boolean,
  "zona_id": string | null,
  "zona_nombre": string | null,
  "oficina_id": string | null,
  "oficina_nombre": string | null,
  "iniciales": string,
  "ultimo_acceso": string,
  "creado_en": string,
  "recomendaciones_ia": boolean,
  "equipos_responsable": unknown[],
  "historial_responsabilidad": unknown[],
  "tickets_creados": number,
  "tickets_afectado": number,
  "tickets_activos": number,
  "horario": {
    "dias": {
      "1": {
        "tramos": {
            "entrada": string,
            "salida": string,
          }[],
        "libre": boolean,
      },
      "2": {
        "tramos": {
            "entrada": string,
            "salida": string,
          }[],
        "libre": boolean,
      },
      "3": {
        "tramos": {
            "entrada": string,
            "salida": string,
          }[],
        "libre": boolean,
      },
      "4": {
        "tramos": {
            "entrada": string,
            "salida": string,
          }[],
        "libre": boolean,
      },
      "5": {
        "tramos": {
            "entrada": string,
            "salida": string,
          }[],
        "libre": boolean,
      },
    },
  },
  "carga_actual": number,
  "especiales": unknown[],
  "permisos": {
    "equipos.crear": boolean,
    "equipos.editar": boolean,
    "equipos.eliminar": boolean,
    "equipos.importar": boolean,
    "equipos.acciones_masivas": boolean,
    "equipos.opciones_avanzadas": boolean,
    "equipos.marcar_no_aplica": boolean,
    "equipos.campanas": boolean,
    "org.editar": boolean,
    "usuarios.editar": boolean,
    "tickets.reasignar": boolean,
    "tickets.cerrar_reabrir": boolean,
    "tickets.eliminar": boolean,
    "kb.editar": boolean,
    "reportes.ver": boolean,
    "exportar": boolean,
    "analitica.ver": boolean,
    "horarios.editar_propio": boolean,
    "horarios.editar_todos": boolean,
    "vistas.compartidas": boolean,
  },
}

/** Respuesta de `GET /usuarios/buscar?texto=a` */
export type RespuestaUsuariosBuscar = {
  "items": {
      "id": string,
      "nombre": string,
      "iniciales": string,
      "email": string,
      "oficina_nombre": string,
      "zona_nombre": string,
      "es_registrado": boolean,
      "activo": boolean,
    }[],
}

/** Respuesta de `GET /usuarios/companeros` */
export type RespuestaUsuariosCompaneros = {
  "items": unknown[],
  "ambito": string,
  "puede_cambiar_ambito": boolean,
}

/** Respuesta de `GET /vistas-guardadas` */
export type RespuestaVistasGuardadas = {
  "items": {
      "nombre": string,
      "vista": string,
      "filtros": {
        "prioridad": string,
        "sla": string,
        "estado": string,
        "tecnico_id": string,
        "zona_id": string,
        "solo_abiertos": boolean,
      },
      "columnas": unknown[],
      "compartida": boolean,
      "creada_por": string,
      "creada_por_nombre": string,
      "creado_en": string,
      "demo": boolean,
      "id": string,
      "puede_editar": boolean,
    }[],
}

/** Respuesta de `GET /zonas` */
export type RespuestaZonas = {
  "items": {
      "id": string,
      "nombre": string,
      "nombre_normalizado": string,
      "descripcion": string | null,
      "activa": boolean,
      "creado_en": string,
      "creado_por": string,
      "actualizado_en": string,
      "demo": boolean,
      "total_oficinas": number,
      "total_usuarios": number,
      "total_equipos": number,
    }[],
}

/** Respuesta de `GET /zonas/{zona_id}` */
export type RespuestaZonasPorzona_id = {
  "id": string,
  "nombre": string,
  "descripcion": string,
  "activa": boolean,
  "creado_en": string,
  "total_oficinas": number,
  "total_usuarios": number,
  "total_equipos": number,
  "tickets_abiertos": number,
  "tickets_periodo": number,
  "tiempo_medio_resolucion_min": number,
  "categorias_frecuentes": {
      "categoria": string,
      "total": number,
    }[],
  "equipos_con_mas_fallas": {
      "id": string,
      "nombre": string,
      "tickets": number,
    }[],
  "completitud_inventario": number,
  "oficinas": {
      "_id": string,
      "nombre": string,
      "nombre_normalizado": string,
      "zona_id": string,
      "zona_nombre": string,
      "descripcion": string,
      "activa": boolean,
      "creado_en": string,
      "creado_por": string,
      "actualizado_en": string,
      "demo": boolean,
      "total_usuarios": number,
      "total_equipos": number,
    }[],
  "puede_crear_oficina": boolean,
}

/** Respuesta de `GET usuario:/auth/preferencia-ia` */
export type RespuestaUsuarioAuthPreferenciaIa = {
  "recomendaciones_ia": boolean,
  "ia_global_activa": boolean,
  "recomendaciones_globales": boolean,
  "recomendaciones_personales": boolean,
  "recomendaciones_visibles": boolean,
  "aprendizaje_activo": boolean,
  "proveedor_disponible": boolean,
  "modelo": string | null,
}

/** Respuesta de `GET usuario:/equipos/mis` */
export type RespuestaUsuarioEquiposMis = {
  "por_conjunto": {
      "conjunto": string,
      "equipos": {
          "id": string,
          "tipo": string,
          "nombre_equipo": string,
          "codigo_patrimonial": string,
          "marca": string | null,
          "modelo": string | null,
          "estado": string,
          "propiedad": string,
          "oficina_id": string,
          "oficina_nombre": string,
          "zona_id": string,
          "zona_nombre": string,
          "conjunto_id": string,
          "conjunto_nombre": string,
          "responsable_id": string,
          "responsable_nombre": string,
          "uso_comun": boolean,
          "completitud": number,
          "faltantes": number,
          "campos_faltantes": unknown[],
          "opciones_avanzadas": boolean,
          "creado_en": string,
        }[],
    }[],
  "uso_comun_oficina": {
      "id": string,
      "tipo": string,
      "nombre_equipo": string,
      "codigo_patrimonial": string,
      "marca": string | null,
      "modelo": string | null,
      "estado": string,
      "propiedad": string,
      "oficina_id": string,
      "oficina_nombre": string,
      "zona_id": string,
      "zona_nombre": string,
      "conjunto_id": string,
      "conjunto_nombre": string,
      "responsable_id": string,
      "responsable_nombre": string,
      "uso_comun": boolean,
      "completitud": number,
      "faltantes": number,
      "campos_faltantes": string[],
      "opciones_avanzadas": boolean,
      "creado_en": string,
    }[],
  "conjuntos": {
      "id": string,
      "nombre": string,
      "oficina_nombre": string,
      "numero": number,
    }[],
}

/** Respuesta de `GET usuario:/mi-perfil` */
export type RespuestaUsuarioMiPerfil = {
  "id": string,
  "nombre": string,
  "email": string,
  "telefono": string | null,
  "anexo": string | null,
  "cargo": string,
  "rol": string,
  "activo": boolean,
  "zona_id": string,
  "zona_nombre": string,
  "oficina_id": string,
  "oficina_nombre": string,
  "iniciales": string,
  "ultimo_acceso": string,
  "creado_en": string,
  "recomendaciones_ia": boolean,
  "equipos_responsable": {
      "id": string,
      "nombre": string,
      "tipo": string,
      "codigo_patrimonial": string,
      "estado": string,
      "oficina_nombre": string,
      "conjunto_nombre": string,
      "completitud": number,
      "opciones_avanzadas": boolean,
    }[],
  "historial_responsabilidad": {
      "conjunto_id": string,
      "responsable_id": string,
      "responsable_nombre": string,
      "inicio": string,
      "fin": string | null,
      "motivo": string,
      "usuario_id": string | null,
      "usuario_nombre": string,
      "fecha": string,
    }[],
  "tickets_creados": number,
  "tickets_afectado": number,
  "tickets_activos": number,
  "horario": {
    "dias": Record<string, never>,
  },
  "carga_actual": number,
  "especiales": unknown[],
  "permisos": {
    "equipos.crear": boolean,
    "equipos.editar": boolean,
    "equipos.eliminar": boolean,
    "equipos.importar": boolean,
    "equipos.acciones_masivas": boolean,
    "equipos.opciones_avanzadas": boolean,
    "equipos.marcar_no_aplica": boolean,
    "equipos.campanas": boolean,
    "org.editar": boolean,
    "usuarios.editar": boolean,
    "tickets.reasignar": boolean,
    "tickets.cerrar_reabrir": boolean,
    "tickets.eliminar": boolean,
    "kb.editar": boolean,
    "reportes.ver": boolean,
    "exportar": boolean,
    "analitica.ver": boolean,
    "horarios.editar_propio": boolean,
    "horarios.editar_todos": boolean,
    "vistas.compartidas": boolean,
  },
  "permisos_efectivos": string[],
}

/** Respuesta de `GET usuario:/tickets?solo_mios=1` */
export type RespuestaUsuarioTickets = {
  "items": {
      "id": string,
      "codigo": string,
      "asunto": string,
      "descripcion": string,
      "estado": string,
      "prioridad": string,
      "origen": string,
      "categoria": string,
      "reportante_id": string,
      "reportante_nombre": string,
      "afectado_id": string,
      "afectado_nombre": string,
      "zona_id": string,
      "zona_nombre": string,
      "oficina_id": string,
      "oficina_nombre": string,
      "activo_id": string,
      "activo_nombre": string,
      "conjunto_id": string,
      "conjunto_nombre": string,
      "tecnico_id": string,
      "tecnico_nombre": string,
      "creado_en": string,
      "actualizado_en": string,
      "sla": {
        "activo": boolean,
        "estado": string,
        "minutos_restantes": number | null,
        "minutos_transcurridos": number,
        "minutos_retraso": number,
        "modo": string,
        "minutos_responder_restantes": number | null,
        "minutos_resolver_restantes": number | null,
        "responder_en": string,
        "resolver_en": string,
        "pausado": boolean,
        "progreso": number,
      },
      "tiempo_resolucion_min": unknown,
      "aceptacion": {
        "consta": boolean,
        "en": string | null,
        "minutos": number | null,
        "plazo_minutos": number | null,
        "cumplio": boolean | null,
        "reconstruido": boolean,
      },
      "confianza_ia": unknown,
      "mensajes_no_leidos": number,
      "satisfaccion": unknown,
      "sla_incumplido": boolean,
      "tiene_chat": boolean,
      "detectado_por_tecnico": boolean,
    }[],
  "total": number,
  "pagina": number,
  "por_pagina": number,
  "total_paginas": number,
}

/** Respuesta de `GET usuario:/usuarios/companeros` */
export type RespuestaUsuarioUsuariosCompaneros = {
  "items": {
      "id": string,
      "nombre": string,
      "iniciales": string,
      "oficina_id": string,
      "oficina_nombre": string,
      "es_registrado": boolean,
      "activo": boolean,
    }[],
  "ambito": string,
  "puede_cambiar_ambito": boolean,
}

/* ═══════════ Parámetros de consulta declarados por la API ═══════════ */

/** Parámetros de `GET /api/zonas` */
export type ConsultaZonas = {
  "solo_activas"?: boolean
}

/** Parámetros de `GET /api/oficinas` */
export type ConsultaOficinas = {
  "zona_id"?: string
  "solo_activas"?: boolean
}

/** Parámetros de `GET /api/usuarios` */
export type ConsultaUsuarios = {
  "zona_id"?: string
  "oficina_id"?: string
  "rol"?: string
  "solo_activos"?: boolean
  "texto"?: string
  "pagina"?: number
  "por_pagina"?: number
}

/** Parámetros de `GET /api/usuarios/buscar` */
export type ConsultaUsuariosBuscar = {
  "texto"?: string
  "limite"?: number
}

/** Parámetros de `GET /api/usuarios/companeros` */
export type ConsultaUsuariosCompaneros = {
  "zona_id"?: string
  "texto"?: string
  "otra_oficina"?: boolean
}

/** Parámetros de `GET /api/conjuntos` */
export type ConsultaConjuntos = {
  "zona_id"?: string
  "oficina_id"?: string
  "texto"?: string
}

/** Parámetros de `GET /api/conjuntos/siguiente-nombre` */
export type ConsultaConjuntosSiguienteNombre = {
  "oficina_id"?: string
  "base"?: string
}

/** Parámetros de `GET /api/activos` */
export type ConsultaActivos = {
  "zona_id"?: string
  "oficina_id"?: string
  "tipo"?: string
  "estado"?: string
  "propiedad"?: string
  "responsable_id"?: string
  "solo_uso_comun"?: string
  "solo_faltantes"?: string | boolean
  "solo_opciones_avanzadas"?: string
  "conjunto_id"?: string
  "texto"?: string
  "pagina"?: number
  "por_pagina"?: number
  "vista"?: string
}

/** Parámetros de `GET /api/equipos/por-codigo` */
export type ConsultaEquiposPorCodigo = {
  "texto"?: string
  "limite"?: number
}

/** Parámetros de `GET /api/equipos/buscar` */
export type ConsultaEquiposBuscar = {
  "texto"?: string
  "zona_id"?: string
  "limite"?: number
}

/** Parámetros de `GET /api/equipos/sugerencias` */
export type ConsultaEquiposSugerencias = {
  "campo"?: string
  "tipo"?: string
  "marca"?: string
  "limite"?: number
}

/** Parámetros de `GET /api/calidad-inventario` */
export type ConsultaCalidadInventario = {
  "zona_id"?: string
  "oficina_id"?: string
  "tipo"?: string
}

/** Parámetros de `GET /api/importacion` */
export type ConsultaImportacion = {
  "limite"?: number
}

/** Parámetros de `GET /api/tickets` */
export type ConsultaTickets = {
  "zona_id"?: string
  "oficina_id"?: string
  "tecnico_id"?: string
  "activo_id"?: string
  "sla"?: string
  "texto"?: string
  "fecha_desde"?: string
  "fecha_hasta"?: string
  "vista"?: string
  "solo_mios"?: boolean
  "pagina"?: number
  "por_pagina"?: number
  "orden"?: string
  "solo_abiertos"?: boolean
}

/** Parámetros de `GET /api/tickets/{ticket_id}/mensajes` */
export type ConsultaTicketsPorticket_idMensajes = {
  "desde"?: string
}

/** Parámetros de `GET /api/ia/sugerencias-reporte` */
export type ConsultaIaSugerenciasReporte = {
  "tipo_problema"?: string
  "descripcion"?: string
  "urgencia"?: string
  "activo_tipo"?: string
}

/** Parámetros de `GET /api/notificaciones` */
export type ConsultaNotificaciones = {
  "limite"?: number
  "solo_no_leidas"?: boolean
}

/** Parámetros de `GET /api/equipo-ti/calendario` */
export type ConsultaEquipoTiCalendario = {
  "desde"?: string
  "hasta"?: string
}

/** Parámetros de `GET /api/ausencias` */
export type ConsultaAusencias = {
  "tecnico_id"?: string
}

/** Parámetros de `GET /api/kb/articulos` */
export type ConsultaKbArticulos = {
  "categoria"?: string
  "texto"?: string
  "pagina"?: number
  "por_pagina"?: number
  "orden"?: string
}

/** Parámetros de `GET /api/campanas/{campana_id}/items` */
export type ConsultaCampanasPorcampana_idItems = {
  "zona_id"?: string
  "oficina_id"?: string
  "estado"?: string
  "solo_pendientes"?: boolean
  "texto"?: string
  "pagina"?: number
  "por_pagina"?: number
}

/** Parámetros de `GET /api/campanas/versiones/comparar` */
export type ConsultaCampanasVersionesComparar = {
  "anio_a"?: number
  "anio_b"?: number
}

/** Parámetros de `GET /api/analitica/panel` */
export type ConsultaAnaliticaPanel = {
  "periodo"?: string
  "desde"?: string
  "hasta"?: string
  "zona_id"?: string
  "oficina_id"?: string
  "categoria"?: string
  "tecnico_id"?: string
  "tipo_activo"?: string
}

/** Parámetros de `GET /api/auditoria` */
export type ConsultaAuditoria = {
  "accion"?: string
  "entidad"?: string
  "usuario_id"?: string
  "resultado"?: string
  "desde"?: string
  "hasta"?: string
  "pagina"?: number
  "por_pagina"?: number
}
