# Helpdesk Triage Agent

[![CI](https://github.com/ArturDev98/helpdesk-triage-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/ArturDev98/helpdesk-triage-agent/actions/workflows/ci.yml) ![Licencia MIT](https://img.shields.io/badge/licencia-MIT-blue)

Agente que hace el primer y segundo nivel de una mesa de ayuda: lee los tickets abiertos, los clasifica,
reconoce si el problema ya es conocido (un issue de desarrollo o un ticket anterior ya resuelto) y, si no
lo es, revisa el código del módulo afectado para proponer la causa probable. Publica el resultado en un
hilo por ticket en el chat del equipo y mantiene un dashboard con el historial.

No modifica nada: ni la herramienta de tickets, ni el tracker, ni el código, ni la base de datos.

## Pruébalo

```bash
python -m triage --dry-run          # demo con el cerebro offline: sin API, sin guardar, salida en consola
python -m triage                    # ciclo real: guarda en data/triage.db y genera data/dashboard.html
python -m unittest discover -s tests -t .
```

Python 3.11+ y solo la biblioteca estándar. Para usar Claude: `pip install -r requirements.txt`, cambia
`[brain] type = "claude"` en `config.toml` y deja la llave en `ANTHROPIC_API_KEY` (o inicia sesión con `ant auth login`).

La demo es una tienda en línea ficticia: 13 tickets (4 cerrados con su solución), 3 issues conocidos y un
código pequeño con fallas sembradas (`demo/codebase/tienda/`). Ejemplos de lo que sale:

| Ticket | Qué hace el agente |
|---|---|
| El cupón no descuenta con productos en oferta | Lo vincula al issue TIENDA-101, que ya está en desarrollo, y no gasta análisis |
| Pago PSE pendiente con el dinero debitado | Reconoce que ya pasó (T-1002) y propone la misma solución |
| Cobran envío en un pedido de 150.000 justos | Señala `tienda/envios.py`, donde está la falla sembrada (`>` en vez de `>=`) |
| ¿Cómo exporto el reporte de ventas? | Consulta: respuesta con la guía, sin tocar código |
| El servidor de pruebas no responde | Operativo: a infraestructura |

## Cómo funciona

```
fuente de tickets ──> redacción de datos personales ──> triage ──> relación ──┬──> acción + chat + dashboard
                                                                               └──> diagnóstico en el código ─┘
memoria de cerrados (SQLite) ──────────────────────────────────────> relación
```

| Paso | Qué hace | Decisión de diseño |
|---|---|---|
| Fuente | `TicketSource` / `IssueSource` (protocolos) | La demo lee JSON; conectar SysAid, Zendesk, Jira SM, GLPI o GitHub Issues es otra clase con tres métodos. |
| Redacción | Correos, teléfonos, documentos y tarjetas salen antes de llegar al modelo, al chat o a la base | El solicitante se descarta en la fuente; nunca se guarda. Los montos con puntos de miles se respetan. |
| Triage | Categoría, módulo, severidad, resumen y si vale la pena mirar código | Esfuerzo `low`: es clasificación. |
| Relación | Preselección TF-IDF (sin dependencias) de issues y tickets cerrados; el modelo decide si es la misma falla | Una llamada barata evita un diagnóstico caro. El modelo no puede citar un candidato que no se le dio. |
| Diagnóstico | Búsqueda de archivos por palabras del ticket y del módulo; fragmentos numerados al modelo | Esfuerzo `high`. Devuelve hipótesis, archivos, pasos para confirmar y la respuesta para el usuario. |
| Memoria | Los tickets que se cierran se guardan con su solución real | "Esto ya pasó" sale de la mesa misma, no de una base de conocimiento que alguien mantenga. |
| Chat | Un hilo por ticket (`threadKey` en Google Chat), Slack o consola | 4xx se descarta; 429 y 5xx se reintentan en el siguiente ciclo. |
| Dashboard | Un solo HTML con los datos embebidos: KPIs, semanas, módulos, detalle con la solución real al lado del diagnóstico | Se abre sin servidor y se puede adjuntar a un correo. |

### Con Claude

- Salidas estructuradas (`output_config.format` con JSON Schema): nada de parsear texto libre.
- El prompt de sistema es el mismo para todos los tickets, así la caché de prompts lo reutiliza.
- Si el modelo declina o la respuesta se corta, el ticket queda "para revisión manual" con una alerta en el chat.
- Fallbacks del lado del servidor activados (`fallbacks: "default"`), por si una clasificación de seguridad rechaza un ticket legítimo.
- Los prompts son genéricos; lo propio de cada empresa va en un perfil (`profiles/tienda.md`) con secciones `# @NOMBRE`, `# @DOMINIO`, `# @MODULOS` y `# @REGLAS`.

El cerebro offline (palabras clave + similitud) existe para que la demo y las pruebas corran sin llave y
con resultados deterministas; su "diagnóstico" solo señala el archivo, no razona sobre él.

## Adaptarlo a tu mesa

1. Implementa `TicketSource` y `IssueSource` para tus herramientas (ver `triage/sources.py`).
2. Escribe tu perfil en `profiles/` y apunta `code_paths` a un clon de solo lectura de tus repos.
3. Ajusta `[modules.*]` con las palabras que usan tus usuarios para cada módulo.
4. Pon la URL del webhook en `CHAT_WEBHOOK_URL` y `[chat] style = "google-chat"` o `"slack"`.
5. Prográmalo cada 15 minutos (cron o Programador de tareas): cada ciclo procesa solo lo nuevo.

## Estructura

```
triage/
  sources.py     protocolos de fuente + implementación JSON
  redact.py      datos personales fuera
  brains.py      ClaudeBrain (API) y OfflineBrain (reglas)
  prompts.py     prompts genéricos + secciones del perfil
  similarity.py  TF-IDF para preseleccionar candidatos
  codesearch.py  archivos y fragmentos relevantes del código
  pipeline.py    el ciclo completo
  store.py       SQLite: tickets, resultados, memoria
  notify.py      chat
  dashboard.py   + dashboard.html
prompts/         triage, relación y diagnóstico
profiles/        lo propio de cada proyecto
demo/            tickets, issues y código ficticios
tests/           unittest (Claude se prueba con un cliente falso)
```

## Límites

- Los nombres propios dentro del texto libre no se detectan con expresiones regulares.
- La búsqueda de código es por palabras; en repos grandes conviene un índice (ripgrep, embeddings) o
  darle al modelo herramientas de lectura en un bucle de agente.
- Es un asistente para la persona de la mesa: propone, no cierra tickets ni escribe al usuario por su cuenta.

## Licencia

MIT. Ver [LICENSE](LICENSE).
