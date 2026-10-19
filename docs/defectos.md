# Defectos encontrados

Registro de los defectos detectados durante el proyecto. La plantilla completa está en `plantilla_defecto.md`; acá se resume cada defecto con su causa, su corrección y su estado.

| ID | Título | Capa | Severidad | Estado |
|---|---|---|---|---|
| DEF-001 | Omisión de treks en listas largas | Modelo / prompt | Grave | Corregido y verificado (ciclo 2) |
| DEF-002 | Textos por defecto de la interfaz del chat | Configuración | Leve | Corregido |
| DEF-003 | La herramienta de prestadores devuelve un solo resultado erróneo | Herramienta / datos | Grave | Corregido |
| DEF-004 | Conteo incorrecto en listas | Modelo / datos | Grave | Abierto: reducido a 1 de 3 ejecuciones |
| DEF-005 | Muletillas que exponen el funcionamiento interno | Modelo / prompt | Leve | Abierto: 9,8 % de las respuestas y 12 de los 16 casos que no aprobaron en el ciclo 2 |
| DEF-006 | Bucle de herramientas por un filtro mal aplicado | Configuración | Grave | Corregido |
| DEF-007 | No vuelve a consultar la herramienta en el segundo turno | Modelo / prompt | Leve | Abierto: ahora se detecta automáticamente |
| DEF-008 | El chat público expone los pasos intermedios del agente | Configuración | Grave | Corregido y verificado |

---

## DEF-001: Omisión de treks en listas largas

- **Casos:** TC13, TC14 (ciclo 1) y TC03 (ciclo 2).
- **Qué pasó:** al filtrar, el agente omitía filas que cumplían la condición. En el ciclo 1 omitió el Cerro Wank en "treks fáciles en La Cumbrecita", en las dos formulaciones de la pregunta. En el ciclo 2 omitió la Cascada Cinco Chorros en la lista de dificultad alta.
- **Causa probable:** el modelo pierde elementos al listar a partir de muchas filas devueltas por la herramienta.
- **Corrección:** regla en el prompt (v8) que obliga a decir cuántos resultados hay antes de listarlos y a verificar que la lista coincida.
- **Estado:** verificado en el ciclo 2: TC03, TC13 y TC14 listan todos los treks en las 9 ejecuciones.

## DEF-002: Textos por defecto de la interfaz del chat

- **Caso:** TC53 (prueba manual en la interfaz).
- **Qué pasó:** el chat público mostraba los textos por defecto de n8n, en inglés ("Hi there! 👋 My name is Nathan", "We're here to help you 24/7"), que contradecían la identidad del agente y prometían una disponibilidad no garantizada.
- **Causa:** configuración del Chat Trigger, no del modelo. El script de pruebas por webhook no puede detectarlo porque no ve la interfaz.
- **Corrección:** mensaje inicial, título, subtítulo y placeholder configurados en el Chat Trigger, en español.
- **Estado:** corregido.

## DEF-003: La herramienta de prestadores devuelve un solo resultado erróneo

- **Casos:** prueba exploratoria y TC62.
- **Qué pasó:** ante cualquier pedido de guías, el agente respondía que no había prestadores en la zona y mostraba siempre al mismo prestador, "con localidad no especificada".
- **Causa:** el nodo `buscar_prestadores` tenía un filtro por localidad sin valor. El filtro buscaba celdas vacías y encontraba la única fila del listado sin localidad. Además, las localidades no coincidían entre los dos archivos ("Villa Las Rosas" frente a "Villa de las Rosas", entre otras).
- **Diagnóstico:** el agente no alucinaba: respondía fielmente lo que le devolvía la herramienta. Se detectó revisando el log de la ejecución, no el texto de la respuesta.
- **Corrección:** valor del filtro definido por el modelo, celda vacía completada con "Sin especificar" y localidades unificadas entre los dos archivos.
- **Estado:** corregido.

## DEF-004: Conteo incorrecto de treks en Capilla del Monte

- **Caso:** TC02 (ciclo 2, 3 ejecuciones).
- **Qué pasó:** en las 3 ejecuciones, el agente dijo que había "tres" treks en Capilla del Monte, cuando son cuatro. En una ejecución omitió el Dique El Cajón; en las otras dos lo agregó después de la lista como "también está…".
- **Causa probable:** el modelo no considera el Dique El Cajón como un trek, posiblemente porque las notas del Cerro Uritorco lo mencionan como vista desde la cumbre.
- **Corrección:** regla 11 en el prompt (v11): todos los registros son treks, aunque su nombre sea un dique o aparezca mencionado en otro trek. TC02 ahora también verifica que el número dicho sea 4.
- **Estado:** en el ciclo 2, TC02 dijo "tres" y listó cuatro en 1 de 3 ejecuciones. El defecto bajó de 3 de 3 a 1 de 3, pero sigue abierto: es intermitente.

## DEF-005: Muletillas que exponen el funcionamiento interno

- **Casos:** TC05, TC18, TC54 y pruebas exploratorias.
- **Qué pasó:** el agente se refiere a su información con expresiones como "la tabla", "tengo registrados", "no tengo ese dato cargado" o "entre los que tengo disponibles".
- **Causa:** el modelo tiende a explicitar sus limitaciones. Prohibir cada palabra reduce la frecuencia, pero aparecen variantes nuevas.
- **Corrección parcial:** reglas en la sección "CÓMO HABLAR" (v4, v6, v10 y v11), incluida una instrucción positiva sobre qué hacer en su lugar.
- **Estado:** abierto. En el ciclo 2 aparecieron en 17 de 174 respuestas (9,8 %), por ejemplo "tengo registrados 75 treks" (TC41, en las 3 ejecuciones) o "marcado como ejemplo en la fuente" (TC12).
- **Recalificación (12 de octubre de 2026):** en el ciclo 2, estas expresiones se marcaron como falla en algunos casos y como aprobado en otros. Ahora las controla un criterio único y automatizado en todas las respuestas (`treks_qa/evaluacion.py`). Con ese criterio, 12 de los 16 casos que no aprueban fallan por este defecto. Detalle en el [informe de resultados](informe_resultados.md#recalificación-con-criterio-único).

## DEF-006: Bucle de herramientas por un filtro mal aplicado

- **Casos:** TC05 y TC03, en una regresión.
- **Qué pasó:** con un trek inexistente ("Cerro Áspero"), el agente llamó a la herramienta una y otra vez hasta alcanzar el límite de 10 iteraciones de n8n, y la ejecución terminó en error. En la misma corrida, TC03 devolvió una lista incompleta.
- **Causa:** `buscar_treks` tenía un filtro por localidad definido por el modelo. Para preguntas por nombre o listas completas, el filtro devolvía vacío y el agente reintentaba con otras variantes.
- **Corrección:** se quitó el filtro de `buscar_treks` (se mantiene en `buscar_prestadores`, donde siempre se busca por zona) y se agregó al prompt la regla de no reintentar una herramienta que devuelve vacío o error. También se hizo que el script registre el error de un caso y siga con los demás.
- **Estado:** corregido. Además del defecto funcional, cada iteración del bucle reenvía todo el contexto al modelo y multiplica el costo.

## DEF-007: No vuelve a consultar la herramienta en el segundo turno

- **Caso:** TC39 (ciclo 2, 3 de 3 ejecuciones).
- **Qué pasó:** a "¿Y la distancia?", después de preguntar por el Uritorco, el agente respondió correctamente pero desde la memoria de la conversación, sin consultar la herramienta, aunque el prompt lo exige.
- **Riesgo:** si los datos cambian durante la conversación, o la memoria tiene un dato incompleto, la respuesta puede quedar desactualizada (ver TC40).
- **Detección automática (19 de octubre de 2026):** desde la evaluación de trayectoria, el runner lo detecta solo. En la corrida de validación, TC39 registró `T1: buscar_treks() → 75 filas | T2: —` y falló por "T2: no llamó buscar_treks" (`results/etapa2_validacion_trayectoria.csv`).
- **Estado:** abierto.

## DEF-008: El chat público expone los pasos intermedios del agente

- **Detección:** prueba exploratoria en el chat público, 12 de octubre de 2026, a partir de la auditoría del workflow.
- **Qué pasó:** con *Return Intermediate Steps* activado en el AI Agent, el Chat Trigger público y *Response Mode* en "When Last Node Finishes", la respuesta HTTP que recibe el navegador incluye `intermediateSteps`. En DevTools (Network → Preview) se ven los nombres de las herramientas (`buscar_treks`, `buscar_prestadores`), sus argumentos (`values0_Value: "Tanti"`) y un registro con bloques de razonamiento del modelo (`thinking`). El workflow de pruebas, copia del público antes de la corrección, confirmó que también incluye las filas devueltas por cada herramienta (campo `observation`): la tabla completa de 75 treks (unos 48.000 caracteres) y todos los prestadores de la localidad buscada, por ejemplo 8 en Tanti, aunque la respuesta muestra solo 5.
- **Por qué no lo detectaron las pruebas:** TC29, TC30 y TC31 evalúan solo el texto de la respuesta, y ahí el agente se niega correctamente a revelar su configuración. La filtración ocurre por otro canal.
- **Riesgo:** expone la configuración que el prompt protege y, si incluye las filas devueltas, los contactos de prestadores sin el límite de 5. Hoy n8n corre en `localhost`, así que el impacto real es bajo mientras no se publique el chat.
- **Corrección (19 de octubre de 2026):** se separaron dos workflows. El público tiene *Return Intermediate Steps* apagado. El de pruebas lo mantiene activado para evaluar la trayectoria, usa el modo *Embedded Chat* y está protegido con *Basic Auth*.
- **Verificación:** `scripts/verificar_chat_publico.py` envía una pregunta que obliga a usar ambas herramientas y falla si la respuesta del chat público contiene `intermediateSteps`, nombres de herramientas u `observation`. Resultado del 19 de octubre de 2026: OK.
- **Estado:** corregido y verificado.

## Observaciones sobre el prompt

### OBS-001: Instrucciones contradictorias sobre "figura"

- **Detección:** al definir el criterio único de recalificación, 12 de octubre de 2026.
- **Qué pasa:** el prompt v12 dice en la sección de fuentes *"Podés informar `dificultad_fuente` tal como figura"* y en "Cómo hablar" *"No uses expresiones como 'figura'"*. El modelo recibe dos instrucciones incompatibles para el mismo caso (informar la escala original de la fuente).
- **Efecto:** en TC47 y TC48 el agente cita la escala de la fuente con "figura", siguiendo la primera instrucción. Con la regla literal serían fallas; el criterio único las acepta cuando la oración menciona la fuente.
- **Capa:** prompt. No es un error del modelo.
- **Corrección propuesta (prompt v13):** reemplazar la primera frase por *"Podés informar `dificultad_fuente` con el texto de la fuente, por ejemplo: 'En la escala de la fuente es 20 HKG / 35 RNG'"*, para que la única instrucción sobre "figura" sea no usarla.
- **Estado:** abierta.

---

## Hallazgos de calidad en las fuentes de datos

Problemas encontrados en las fuentes oficiales y periodísticas al construir el dataset. Ninguno se copió al dataset sin resolver.

| Fuente | Hallazgo | Tratamiento |
|---|---|---|
| Córdoba Turismo, página Ecoturismo | Altura de Los Gigantes en dos valores distintos (2374 y 2379 m) | Se tomó 2374 y se documentó el conflicto en las notas |
| Córdoba Turismo, fichas de senderos | Dos fichas de la Cara del Indio con datos contradictorios (2,84 km solo ida frente a 7 km ida y vuelta) | Se usó la ficha más completa y se dejó el conflicto anotado |
| Córdoba Turismo, ficha de Paz y Bien | "Pendientes de 440 grados", un valor físicamente imposible | No se copió al dataset |
| Córdoba Turismo, ficha de la Reserva Hídrica | 0 m de desnivel positivo con 53 m entre la altitud máxima y la mínima | Se mantuvo el dato con la observación |
| Córdoba Turismo, fichas de senderos | Cuatro escalas de dificultad distintas (verbal, HKG/RNG, BYC) | Solo se tradujeron a baja/media/alta las verbales; el resto queda en `dificultad_fuente` |
| Fuentes periodísticas | Distancia Córdoba–Capilla del Monte entre 95 y 109 km; altura del Champaquí de 2890 m en una nota (el valor oficial es 2790) | Se priorizó la fuente oficial y se documentaron los rangos |
| Listado de prestadores habilitados | 151 credenciales vencidas, una fecha inexistente (30/02/2027) y 20 filas sin nombre | Se filtraron las credenciales vigentes y se excluyó la fecha inválida |
