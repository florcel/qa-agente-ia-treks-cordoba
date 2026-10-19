# Registro de cambios

Cada cambio de prompt o de dataset es una versión nueva. Los resultados de las pruebas solo son comparables entre ciclos con la misma configuración.

## Configuración por ciclo

| Ciclo | Prompt | Dataset | Entorno | Notas |
|---|---|---|---|---|
| 1 | v1 | v1 (60 treks de ejemplo) | n8n Cloud | Ejecución manual desde el chat |
| 2 | v12 | v8 (75 treks) + prestadores | n8n 2.41.7 local (Docker) | Ejecución automatizada con `run_tests.py`, 3 ejecuciones por caso. `buscar_treks` sin filtros. El archivo de Google se llamaba `treks_cordoba_v9` por un error de nombre; la pestaña usada fue `treks_cordoba_v8` |

## System prompt

| Versión | Cambio | Motivo |
|---|---|---|
| v1 | Prompt inicial: solo datos de la tabla, frases fijas para dato faltante, trek inexistente, fuera de tema y confidencialidad | Diseño inicial |
| v2 | Columnas de altura y fuente | Dataset v2 |
| v3 | Tipo de recorrido y dificultad de la fuente; excepción por coincidencia exacta de nombre; no agregar datos externos; no mencionar estructuras internas | Dataset v3; inconsistencia entre TC10 y TC11; prueba manual del Champaquí |
| v4 | Frases fijas sin la palabra "tabla"; "cómo llegar" fuera de alcance | El agente mencionaba la tabla al usuario |
| v5 | Columnas de acceso, segunda herramienta de prestadores y sección "Cómo llegar y requisitos" | Dataset v4 y listado de prestadores |
| v6 | Prohibición de muletillas tipo "tengo registradas" y de introducciones | DEF-005 |
| v7 | Sección "Conceptos generales" | El agente rechazaba "¿qué es un trekking?" |
| v8 | Decir cuántos resultados hay antes de listar; dar directamente los datos parciales; no usar "figura" ni "según las notas" | DEF-001; TC08 |
| v9 | Columna `destino` y agrupación de rutas | Rutas al Champaquí repetidas en las listas |
| v10 | Cierres que solo ofrecen información disponible | Ofrecimientos de "cómo llegar" sin el dato |
| v11 | Dato faltante distinto de dato no confirmado; no omitir rutas sin confirmar; no generalizar datos entre rutas; todos los registros son treks; recomendación distinta de requisito; prestadores por zona | TC06, TC17, TC21, DEF-004, Cerro La Ventana, DEF-003 |
| v12 | No reintentar herramientas vacías o con error; "no confirmado" en lugar de "de ejemplo", con aclaraciones agrupadas; coincidencia exacta aunque el destino tenga otras rutas; no mostrar ítems descartados ni el razonamiento | DEF-006; TC03; TC10 y TC11; TC16 |

## Dataset de treks

| Versión | Treks | Cambio | Fuente |
|---|---|---|---|
| v1 | 60 | 10 treks iniciales + 50 agregados; datos de ejemplo, con casos de prueba diseñados (homónimos, campos vacíos, empates) | Datos de ejemplo |
| v2 | 62 | Columnas `altura_msnm` y `fuente`; 14 filas verificadas; corrección de nombre (Cerro Charalqueta / Colchiqui); 2 senderos nuevos | Córdoba Turismo, página Ecoturismo |
| v3 | 75 | 13 senderos nuevos; columnas `tipo_recorrido`, `dificultad_fuente` y `desnivel_positivo_m`; rutas oficiales al Champaquí | Fichas técnicas de Córdoba Turismo (API pública del sitio) |
| v4 | 75 | Columnas de acceso: `como_llegar`, `distancia_desde_cordoba_km`, `requisitos`, `recomendaciones`, `fuente_acceso` | Parques Nacionales, Ministerio de Turismo de la Nación y medios |
| v5 | 75 | Duración del Uritorco (7 h) y horarios de ascenso y descenso | Medios (La Nación, Cadena 3) |
| v6 | 75 | Columna `destino` para agrupar rutas; los homónimos de localidades distintas no se agrupan | Decisión de diseño |
| v7 | 75 | El Cerro Mogote se agrupa en el destino Los Gigantes | Resultado de TC03 |
| v8 | 75 | La nota de la ruta desde Villa de las Rosas ya no menciona "la ficha oficial" | El texto de los datos se filtraba en las respuestas |

## Configuración de las herramientas

| Fecha | Cambio | Motivo |
|---|---|---|
| Octubre de 2026 | Filtro por localidad definido por el modelo en `buscar_prestadores` | DEF-003 |
| 6 de octubre de 2026 | Se quitó un filtro por localidad que había quedado en `buscar_treks` | DEF-006. Las corridas hechas con ese filtro no son comparables |
| 19 de octubre de 2026 | Dos workflows: público (sin pasos intermedios) y de pruebas (con pasos intermedios, *Embedded Chat* y *Basic Auth*). El prompt, el modelo y las herramientas son iguales en ambos | DEF-008. Las pruebas automáticas usan el workflow de pruebas |
| 19 de octubre de 2026 | Descripción del parámetro de `buscar_prestadores`: decía "Nombre exacto del trek" aunque el filtro es por `localidad`; ahora pide la localidad y, si el usuario nombra un trek, la localidad de ese trek. En los dos workflows | Contradicción entre la herramienta y el prompt detectada en la auditoría. Antes funcionaba solo porque el prompt lo compensaba. Regresión: TC55, TC56 y TC62 cumplen la trayectoria esperada (`results/etapa2_regresion_prestadores.csv`) |

## Criterio de evaluación

| Fecha | Cambio | Motivo |
|---|---|---|
| 12 de octubre de 2026 | Criterio único para las expresiones prohibidas, aplicado a todas las respuestas y turnos (`treks_qa/evaluacion.py`). "Figura" se acepta solo en una oración que menciona la fuente (OBS-001). La verificación de cada caso compara por inicio de palabra, no confunde un número con otro que lo contiene ("7" con "17") y revisa `not_contains` en todos los turnos | La misma expresión se calificaba distinto según el caso. Ciclo 2 recalificado: de 51 a 42 casos aprobados sobre 58 |
| 12 de octubre de 2026 | Evaluación de trayectoria: columna `herramientas_esperadas` en los casos y verificación automática de herramientas, argumentos y llamadas repetidas en cada turno (`treks_qa/trayectoria.py`). `run_tests.py` guarda la respuesta completa del webhook y la latencia | Antes solo se sabía si el agente había llamado alguna herramienta, sin distinguir cuál ni con qué argumento. No se aplica al ciclo 2, que no guardó las respuestas completas |

## Listado de prestadores

| Versión | Cambio |
|---|---|
| v1 | Filtrado de credenciales vigentes (418 de 570) y normalización de actividades |
| v2 | Localidades unificadas con las del dataset de treks; localidad vacía reemplazada por "Sin especificar" (DEF-003) |

El listado real contiene datos personales de contacto y no se publica en este repositorio. `data/prestadores_ejemplo_anonimizado.csv` conserva su estructura con contactos ficticios.
