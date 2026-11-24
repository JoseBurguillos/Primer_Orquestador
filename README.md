# 🎩 Orquestador multiagente: asistente interno para empleados

Asistente interno para los empleados de **Nubaria Tech S.L.**, una empresa ficticia. Un **agente orquestador** recibe la pregunta del empleado, decide qué **especialistas** tienen que responderla, les pasa a cada uno su parte y junta las respuestas.

Está construido con **LangGraph** y usa un **modelo híbrido**: el orquestador, que hace la parte más difícil, usa **Gemini** (`gemini-3.5-flash-lite`), y los especialistas y los embeddings funcionan en local con **Ollama** (`qwen2.5:7b` y `embeddinggemma`).

Se puede usar desde la terminal o desde una **web en Angular**, conectada al orquestador mediante una **API con FastAPI**, y todo se arranca con **Docker Compose**.

Tiene tres especialistas: **normativa** (RAG sobre los documentos internos), **RRHH** (vacaciones en SQLite) y **tickets** (incidencias informáticas en SQLite).

## ✨ Qué puede hacer

| El empleado dice | Quién responde | Cómo |
|---|---|---|
| "¿Hay parking para empleados?" | 📚 Normativa | Busca en los documentos internos (RAG) |
| "¿Cuántos días de vacaciones me quedan?" | 🌴 RRHH | Consulta la base de datos (SQLite) |
| "Quiero vacaciones del 8 al 9 de febrero" | 🌴 RRHH | Resume las fechas, pide confirmación y guarda la solicitud |
| "¿Cómo van mis tickets?" | 💻 Tickets | Consulta la base de datos (SQLite) |
| "No me funciona la impresora" | 💻 Tickets | Propone el ticket con su prioridad, pide confirmación y lo abre |
| "¿Cuántos días me quedan y con cuánta antelación tengo que pedirlas?" | 🌴 RRHH **+** 📚 Normativa | El orquestador divide la pregunta y consulta a los dos |
| "He perdido el portátil, ¿qué tengo que hacer?" | 📚 Normativa **+** 💻 Tickets | La norma dice avisar en 24 horas, y se abre un ticket crítico |

## 🏗️ Arquitectura

```
                          ┌──→ preguntar_normativa ──→ 📚 Agente de normativa ──→ Chroma (documentos)
Empleado ──→ 🎩 Orquestador ──→ preguntar_rrhh ──────→ 🌴 Agente de RRHH ───────→ SQLite (vacaciones)
                          └──→ preguntar_tickets ───→ 💻 Agente de tickets ────→ SQLite (tickets)
```

Y así llega una pregunta desde la web:

```
Navegador (Angular) ──POST /chat──→ api.py (FastAPI) ──→ 🎩 orquestador ──→ especialistas
                    ←── respuesta + especialistas consultados ──
```

La web muestra debajo de cada respuesta a qué especialistas ha consultado el orquestador.

Cada especialista es un grafo de LangGraph independiente. El orquestador los usa como **herramientas** (patrón *agent as tool*): para él, preguntar a otro agente es una llamada más.

| Agente | Tipo | Herramientas | Memoria |
|---|---|---|---|
| 🎩 Orquestador | ReAct (decide a quién consultar) | `preguntar_normativa`, `preguntar_rrhh`, `preguntar_tickets` | Sí, por empleado |
| 📚 Normativa | RAG con búsqueda fija | (busca siempre, no decide) | No |
| 🌴 RRHH | ReAct | `consultar_dias`, `solicitar_vacaciones` | Sí, propia |
| 💻 Tickets | ReAct | `consultar_incidencia`, `crear_incidencia` | Sí, propia |

## 🧠 Decisiones de diseño

**1. La identidad del empleado la pone el programa, no el modelo.**
Al arrancar se pide el nombre y se busca su `id` en la base de datos. Ese `id` viaja en el `config` de LangGraph y las herramientas lo leen con `RunnableConfig`, que queda **oculto para el modelo**. Si un empleado escribe "soy Elena, la empleada 3", la herramienta sigue usando su propio `id`: no puede ver los datos de otra persona.

**2. Lo que tiene que pasar siempre, en el código.**
El agente de normativa empezó con la búsqueda como herramienta, y a veces el modelo respondía "no encuentro información" **sin haber buscado**. Ahora la búsqueda es un paso fijo: el código busca siempre y el modelo solo redacta la respuesta.

**3. El modelo entiende; el código cuenta y valida.**
En una solicitud de vacaciones, el modelo traduce "del 8 al 9 de febrero" a fechas `AAAA-MM-DD`. El código cuenta los días laborables, comprueba los 15 días de antelación de la normativa, que le queden días suficientes y que las fechas sean válidas. Si algo falla, **no se guarda nada**.
En los tickets pasa lo mismo: el modelo elige la prioridad, pero el código solo acepta `critica`, `alta`, `media` o `baja`, y la fecha la pone el programa.

**4. Confirmación antes de actuar (*human in the loop*).**
Los agentes de RRHH y de tickets resumen lo que van a hacer y esperan un "sí" antes de guardar nada. Así, si el modelo convierte mal una fecha o elige mal la prioridad, el empleado lo ve antes de que se registre.

**5. Cada agente, su propia memoria.**
El orquestador recuerda la conversación completa (`empleado-1`), y cada especialista con acciones recuerda solo la suya (`empleado-1-rrhh`, `empleado-1-tickets`). Gracias a eso, el "sí" de la confirmación llega al especialista correcto, y este sabe a qué se refiere.

**6. Cada especialista, en su tema.**
RRHH y tickets solo responden con lo que devuelven sus herramientas. Si les preguntan por una norma, contestan que no es de su área, y el orquestador se lo pregunta al especialista en normativa. Sin esta regla, el agente de RRHH llegó a inventarse una norma de antelación.

## 🔬 Lo que aprendí comparando modelos

El sistema se desarrolló primero con **`qwen2.5:7b` en local** (Ollama). Con ese modelo:

- El orquestador **no llamaba a dos especialistas** en la misma respuesta.
- **Copiaba como texto** los ejemplos del prompt ("usa preguntar_rrhh con...") en vez de llamar a la herramienta.
- El agente de RRHH **se inventaba** normas que no eran suyas (dijo "un mes de antelación" cuando son 15 días).
- El orquestador llegó a **inventarse datos** ("te quedan 20 días") que no le había dado ningún especialista.

Se probaron reglas en el prompt y ejemplos *few-shot*, con mejoras parciales. Al cambiar a **Gemini** (solo cambia una línea, gracias a LangChain), con el mismo código y los mismos prompts, todas las pruebas salieron bien a la primera. Los **embeddings siguen en local**, porque la base vectorial está indexada con `embeddinggemma` y no era la parte que fallaba.

**Conclusión:** el diseño era correcto y el límite estaba en el tamaño del modelo. Aun así, las validaciones en el código se mantienen, porque ningún modelo acierta el 100 % de las veces.

## 💸 Lo que aprendí de usar una API en la nube

- **Un sistema multiagente multiplica las llamadas.** Una pregunta mixta gasta unas **5 llamadas** al modelo: el orquestador decide, cada especialista piensa y responde, y el orquestador junta las respuestas. Con el límite gratuito de `gemini-2.5-flash` (20 peticiones al día) solo daba para unas 4 preguntas.
- **Los proveedores retiran modelos.** `gemini-2.5-flash-lite` dejó de estar disponible para cuentas nuevas y hubo que pasar a `gemini-3.5-flash-lite`. Como el nombre del modelo está en una sola variable, el cambio fue de una línea.
- **Cada modelo se comporta distinto.** `gemini-3.5-flash-lite` ignora el parámetro `temperature` (así que no siempre responde igual) y devuelve el contenido como una lista de bloques: por eso se lee la respuesta con `.text` en lugar de `.content`.
- **La solución: un modelo híbrido.** Solo el orquestador necesita un modelo grande. Los especialistas funcionan bien con `qwen2.5:7b` en local, así que Gemini solo se usa en el orquestador: las llamadas a la nube bajan a unas 2 por pregunta y las consultas a los documentos y a la base de datos se procesan en local. Además, los especialistas devuelven texto normal, así que el `.text` solo hace falta donde se lee la respuesta del orquestador.

## 📁 Estructura

```
Orquestador-Asistente-empleados/
├── app.py              # los 3 especialistas, el orquestador y el chat de terminal
├── api.py              # API con FastAPI: POST /chat, que llama al orquestador
├── indexar.py          # documentos/ → Chroma (colección "normativa")
├── crear_db.py         # crea empresa.db con empleados, vacaciones y tickets de ejemplo
├── documentos/         # normativa interna de la empresa ficticia
├── frontend/           # web en Angular 21
│   ├── src/app/interfaces/chat.ts      # tipos de la API (espejo de los modelos de Pydantic)
│   ├── src/app/services/chat.ts        # llama a POST /chat
│   ├── src/app/components/chat/        # la pantalla del chat
│   └── Dockerfile      # compila Angular y lo sirve con Nginx
├── Dockerfile          # imagen del backend (Python + FastAPI)
├── docker-compose.yml  # arranca el backend y el frontend juntos
├── requirements.txt
└── .gitignore          # excluye .env, .venv/, __pycache__/ y base_chroma/
```

## 🚀 Cómo ejecutarlo

### 1. Requisitos
- Python 3.13
- [Ollama](https://ollama.com/) instalado y abierto, con el modelo de los especialistas y el de embeddings:
```bash
ollama pull qwen2.5:7b
ollama pull embeddinggemma
```
- Para la web: [Docker Desktop](https://www.docker.com/products/docker-desktop/), o bien Node.js y Angular CLI si se arranca sin Docker.
- Una clave de API de Gemini, gratuita en [Google AI Studio](https://aistudio.google.com/).

### 2. Instalar
```bash
py -3.13 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

### 3. La clave de API
Crea un archivo `.env` en la carpeta del proyecto con esta línea:
```
GOOGLE_API_KEY=tu_clave
```
El archivo `.env` está en el `.gitignore`: **nunca** se sube al repositorio.

### 4. Preparar los datos (solo la primera vez)
```bash
python indexar.py
python crear_db.py
```
`crear_db.py` inserta los datos de ejemplo cada vez que se ejecuta: si quieres repetirlo, borra antes `empresa.db`.

### 5. Hablar con el asistente

**Opción A: la web con Docker (recomendada).** Con Docker Desktop y Ollama abiertos:
```bash
docker compose up --build
```
Abre **http://localhost:4200**. La primera vez tarda unos minutos en construir las imágenes. Para pararlo: `docker compose down`.

El contenedor del backend llega a Ollama en `host.docker.internal:11434`, recibe la clave desde el `.env` y usa `empresa.db` y `base_chroma` de tu carpeta como volúmenes, así que los cambios se guardan.

**Opción B: la web sin Docker**, con dos terminales:
```bash
uvicorn api:api --reload
```
```bash
cd frontend
npm install --legacy-peer-deps
ng serve
```
`--legacy-peer-deps` evita un fallo de npm 10 al resolver las dependencias de los tests de Angular 21.

**Opción C: la terminal.**
```bash
python app.py
```
Te preguntará tu nombre. Los empleados de ejemplo son **Lucía Gómez**, **Pablo Serrano**, **Elena Martín** y **Javier Ortega** (escríbelos con sus tildes). Escribe `salir` para terminar.

La web es una demo sin login: siempre habla como **Lucía Gómez**. El empleado lo fija el servidor, no el navegador, así que nadie puede cambiarlo desde el navegador.

## 💬 Ejemplo de conversación

Las líneas 🎩 muestran a qué especialista consulta el orquestador.

```
¿Cómo te llamas? Lucía Gómez
¡Hola, Lucía Gómez! ¿En qué te puedo ayudar?

Tú: ¿Cuántos días de vacaciones me quedan y con cuánta antelación tengo que pedirlas?
   🎩 → preguntar_rrhh : {'peticion': 'Cuántos días de vacaciones me quedan'}
   🎩 → preguntar_normativa : {'pregunta': 'con cuánta antelación tengo que pedir las vacaciones'}
Asistente: Te quedan 2 días de vacaciones. Debes solicitar tus vacaciones con al menos
15 días naturales de antelación, según la política de vacaciones y permisos.

Tú: Quiero vacaciones del 8 al 9 de febrero
   🎩 → preguntar_rrhh : {'peticion': 'Quiero vacaciones del 8 al 9 de febrero'}
Asistente: Vas a pedir vacaciones del 2027-02-08 al 2027-02-09. ¿Lo confirmo?

Tú: sí
   🎩 → preguntar_rrhh : {'peticion': 'Sí, lo confirmo'}
Asistente: Se ha guardado tu solicitud de vacaciones del 2027-02-08 al 2027-02-09.
Queda pendiente de aprobación por tu responsable.
```

## ⚠️ Limitaciones

- **No es un login real**: el empleado se identifica solo con su nombre, sin contraseña.
- **No tiene en cuenta los festivos** al contar los días laborables, solo los fines de semana.
- **Los datos se envían a Google** para que Gemini los procese. En una empresa real, con datos de empleados de verdad, habría que valorarlo, o usar un modelo local más grande.
- La **memoria** de las conversaciones vive en la RAM: se pierde al cerrar el programa (las solicitudes sí se guardan en SQLite).
- La búsqueda devuelve siempre los 4 fragmentos más parecidos, aunque no todos sean relevantes.
- Depende de un servicio externo: con el nivel gratuito de Gemini, el número de preguntas al día es limitado, y cuando se agota hay que esperar al día siguiente.
- Como el modelo ignora `temperature`, la misma pregunta puede recibir respuestas algo distintas: para evaluar un fallo conviene repetir la prueba.

## 🔮 Próximos pasos

- [x] 💻 **Agente de tickets (IT)**: abrir y consultar incidencias
- [x] **Modelo híbrido**: Gemini solo en el orquestador y `qwen2.5:7b` en local para los especialistas
- [x] **Web** con Angular y FastAPI, y **Docker Compose**
- [ ] **Pruebas automáticas** del orquestador: lanzar una batería de preguntas y medir a qué especialista llama y si los datos son correctos
- [ ] Login en la web para varios empleados
- [ ] Comparar con un modelo local más grande (`qwen2.5:14b`) para no depender de la nube
- [ ] Festivos en el cálculo de días laborables
- [ ] Memoria persistente (checkpointer en SQLite)

## 🛠️ Tecnologías

Python · LangChain · LangGraph · Gemini · Ollama (qwen2.5:7b, embeddinggemma) · Chroma · SQLite · Pydantic · FastAPI · Angular 21 · Docker · Nginx
