# Plantilla de reporte de defectos

Copiá la sección **Plantilla** para cada defecto. Un defecto puede agrupar varios casos de prueba si comparten la causa.

---

## Plantilla

### DEF-XXX: [Título breve: qué hace mal el agente y en qué situación]

| Campo | Valor |
|---|---|
| **ID** | DEF-XXX |
| **Caso(s) de prueba** | TCxx |
| **Categoría** | Corrección de datos / Alucinaciones / Consistencia / Casos límite / Ambiguas o incompletas / Fuera de tema / Prompt injection / Seguridad y respuestas responsables / Uso de la herramienta |
| **Severidad** | Falla leve / Falla grave |
| **Prioridad** | Alta / Media / Baja |
| **Estado** | Abierto / En análisis / Corregido / Verificado / Cerrado / No se corrige |
| **Fecha de detección** | AAAA-MM-DD |
| **Reportado por** | |

#### Configuración al momento de la falla

| Parámetro | Valor |
|---|---|
| Versión de n8n | |
| Proveedor y modelo de LLM | |
| Temperatura | |
| Ventana de Simple Memory | |
| Versión del system prompt | |
| Versión del dataset | |

#### Reproducibilidad

- **Ocurrencias:** X de 3 ejecuciones
- **Session ID(s):**
- **ID de ejecución en n8n:**

#### Pasos para reproducir

1. Iniciar una sesión nueva (session ID nuevo).
2. Enviar: `"..."`
3. (Si es multi-turno) Enviar: `"..."`

#### Resultado esperado

Qué debería haber respondido, según el caso de prueba y el system prompt.

#### Resultado obtenido

Respuesta textual completa del agente (sin recortar):

```text
[pegar respuesta]
```

#### ¿Invocó la herramienta?

Sí / No / No verificable. Indicá cómo se verificó: respuesta del webhook o historial de ejecuciones.

#### Dato de referencia en la tabla

Fila o filas relevantes del dataset, para comparar con la respuesta.

#### Hipótesis de causa

- [ ] System prompt (regla ausente, ambigua o en conflicto)
- [ ] Herramienta (configuración del Google Sheets Tool, filtros, descripción)
- [ ] Memoria (respuesta tomada del historial)
- [ ] Datos (fila mal cargada, formato, campo ambiguo)
- [ ] Modelo (comportamiento no determinista o limitación del LLM)
- [ ] Otra:

#### Evidencia adjunta

Capturas, exportación de la ejecución de n8n o fila del CSV de resultados.

#### Notas y propuesta de corrección

---

## Ejemplo completado (ilustrativo)

> **Atención:** este ejemplo muestra cómo completar la plantilla. **No es un resultado real** de la ejecución de las pruebas. Los defectos reales están en `defectos.md`.

### DEF-000 (ejemplo): Elige una ruta al Champaquí sin avisar que hay varias

| Campo | Valor |
|---|---|
| **ID** | DEF-000 |
| **Caso(s) de prueba** | TC21 |
| **Categoría** | Ambiguas o incompletas |
| **Severidad** | Falla grave |
| **Prioridad** | Alta |
| **Estado** | Abierto |
| **Fecha de detección** | AAAA-MM-DD |
| **Reportado por** | Alan Porcel |

#### Configuración al momento de la falla

| Parámetro | Valor |
|---|---|
| Versión de n8n | [completar] |
| Proveedor y modelo de LLM | [completar] |
| Temperatura | [completar] |
| Ventana de Simple Memory | [completar] |
| Versión del system prompt | v1 |
| Versión del dataset | treks_cordoba_ejemplo.csv (60 filas) |

#### Reproducibilidad

- **Ocurrencias:** 2 de 3 ejecuciones
- **Session ID(s):** tc21-run1, tc21-run3
- **ID de ejecución en n8n:** [completar]

#### Pasos para reproducir

1. Iniciar una sesión nueva.
2. Enviar: `"¿Cuánto dura el Champaquí?"`

#### Resultado esperado

Lista las 4 rutas (Villa Alpina, Villa Yacanto, San Javier, Villa de las Rosas) con su duración, o pregunta a cuál se refiere (regla 3 del system prompt).

#### Resultado obtenido

```text
El Cerro Champaquí dura aproximadamente 14 horas y se suele hacer en 2 días.
```

#### ¿Invocó la herramienta?

Sí, verificado en el historial de ejecuciones de n8n.

#### Dato de referencia en la tabla

| nombre | localidad | duracion_horas |
|---|---|---|
| Cerro Champaquí | Villa Alpina | 14 |
| Cerro Champaquí (desde Villa Yacanto) | Villa Yacanto | 13 |
| Cerro Champaquí (desde San Javier) | San Javier | 12 |
| Cerro Champaquí (desde Villa de las Rosas) | Villa de las Rosas | 12 |

#### Hipótesis de causa

- [x] System prompt: la regla de homónimos no menciona explícitamente nombres que contienen el término buscado.
- [x] Datos: la fila "Cerro Champaquí" (Villa Alpina) coincide exactamente con la búsqueda y las otras no.

#### Evidencia adjunta

Fila TC21 de `resultados_AAAA-MM-DD.csv`.

#### Notas y propuesta de corrección

- Reforzar la regla 3 del system prompt: "si el nombre buscado aparece dentro del nombre de varios treks, listalos todos".
- Opcional: renombrar la fila de Villa Alpina a "Cerro Champaquí (desde Villa Alpina)" para mantener la consistencia del dataset.
- Volver a ejecutar TC21 y TC22–TC23 como regresión.
