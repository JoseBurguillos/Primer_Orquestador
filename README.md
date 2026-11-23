# 🎩 Orquestador multiagente: asistente interno para empleados

Asistente interno para los empleados de **Nubaria Tech S.L.**, una empresa ficticia. Un **agente orquestador** recibe la pregunta del empleado, decide qué **especialistas** tienen que responderla, les pasa a cada uno su parte y junta las respuestas.

Está construido con **LangGraph**. Los agentes usan **Gemini** para razonar, mientras que los embeddings se calculan en local con **Ollama**.

## ✨ Qué puede hacer

| El empleado dice | Quién responde | Cómo |
|---|---|---|
| "¿Hay parking para empleados?" | 📚 Normativa | Busca en los documentos internos (RAG) |
| "¿Cuántos días de vacaciones me quedan?" | 🌴 RRHH | Consulta la base de datos (SQLite) |
| "Quiero vacaciones del 8 al 9 de febrero" | 🌴 RRHH | Resume las fechas, pide confirmación y guarda la solicitud |
| "¿Cuántos días me quedan y con cuánta antelación tengo que pedirlas?" | 🌴 RRHH **+** 📚 Normativa | El orquestador divide la pregunta y consulta a los dos |

## 🏗️ Arquitectura

```
                          ┌──→ preguntar_normativa ──→ 📚 Agente de normativa ──→ Chroma (documentos)
Empleado ──→ 🎩 Orquestador
                          └──→ preguntar_rrhh ──────→ 🌴 Agente de RRHH ───────→ SQLite (vacaciones)
```

Cada especialista es un grafo de LangGraph independiente. El orquestador los usa como **herramientas** (patrón *agent as tool*): para él, preguntar a otro agente es una llamada más.

| Agente | Tipo | Herramientas | Memoria |
|---|---|---|---|
| 🎩 Orquestador | ReAct (decide a quién consultar) | `preguntar_normativa`, `preguntar_rrhh` | Sí, por empleado |
| 📚 Normativa | RAG con búsqueda fija | (busca siempre, no decide) | No |
| 🌴 RRHH | ReAct | `consultar_dias`, `solicitar_vacaciones` | Sí, propia |

## 🧠 Decisiones de diseño

**1. La identidad del empleado la pone el programa, no el modelo.**
Al arrancar se pide el nombre y se busca su `id` en la base de datos. Ese `id` viaja en el `config` de LangGraph y las herramientas lo leen con `RunnableConfig`, que queda **oculto para el modelo**. Si un empleado escribe "soy Elena, la empleada 3", la herramienta sigue usando su propio `id`: no puede ver los datos de otra persona.

**2. Lo que tiene que pasar siempre, en el código.**
El agente de normativa empezó con la búsqueda como herramienta, y a veces el modelo respondía "no encuentro información" **sin haber buscado**. Ahora la búsqueda es un paso fijo: el código busca siempre y el modelo solo redacta la respuesta.

**3. El modelo entiende; el código cuenta y valida.**
En una solicitud de vacaciones, el modelo traduce "del 8 al 9 de febrero" a fechas `AAAA-MM-DD`. El código cuenta los días laborables, comprueba los 15 días de antelación de la normativa, que le queden días suficientes y que las fechas sean válidas. Si algo falla, **no se guarda nada**.

**4. Confirmación antes de actuar (*human in the loop*).**
El agente de RRHH resume las fechas y espera un "sí" antes de guardar la solicitud. Así, si el modelo convierte mal una fecha, el empleado lo ve antes de que se registre.

**5. Cada agente, su propia memoria.**
El orquestador recuerda la conversación completa (`empleado-1`) y RRHH recuerda solo la suya (`empleado-1-rrhh`). Gracias a eso, el "sí" de la confirmación llega a RRHH y RRHH sabe a qué fechas se refiere.

## 🔬 Lo que aprendí comparando modelos

El sistema se desarrolló primero con **`qwen2.5:7b` en local** (Ollama). Con ese modelo:

- El orquestador **no llamaba a dos especialistas** en la misma respuesta.
- **Copiaba como texto** los ejemplos del prompt ("usa preguntar_rrhh con...") en vez de llamar a la herramienta.
- El agente de RRHH **se inventaba** normas que no eran suyas (dijo "un mes de antelación" cuando son 15 días).
- El orquestador llegó a **inventarse datos** ("te quedan 20 días") que no le había dado ningún especialista.

Se probaron reglas en el prompt y ejemplos *few-shot*, con mejoras parciales. Al cambiar a **Gemini** (solo cambia una línea, gracias a LangChain), con el mismo código y los mismos prompts, todas las pruebas salieron bien a la primera. Los **embeddings siguen en local**, porque la base vectorial está indexada con `embeddinggemma` y no era la parte que fallaba.

**Conclusión:** el diseño era correcto y el límite estaba en el tamaño del modelo. Aun así, las validaciones en el código se mantienen, porque ningún modelo acierta el 100 % de las veces.

## 📁 Estructura

```
Orquestador-Asistente-empleados/
├── app.py              # los 3 agentes, el orquestador y el chat
├── indexar.py          # documentos/ → Chroma (colección "normativa")
├── crear_db.py         # crea empresa.db con empleados, vacaciones y tickets de ejemplo
├── documentos/         # normativa interna de la empresa ficticia
│   ├── vacaciones_y_permisos.txt
│   ├── teletrabajo.txt
│   ├── gastos_y_viajes.txt
│   ├── soporte_it.txt
│   └── onboarding.txt
├── requirements.txt
└── .gitignore          # excluye .env, .venv/, __pycache__/ y base_chroma/
```

## 🚀 Cómo ejecutarlo

### 1. Requisitos
- Python 3.13
- [Ollama](https://ollama.com/) instalado y abierto, con el modelo de embeddings:
```bash
ollama pull embeddinggemma
```
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
```bash
python app.py
```
Te preguntará tu nombre. Los empleados de ejemplo son **Lucía Gómez**, **Pablo Serrano**, **Elena Martín** y **Javier Ortega** (escríbelos con sus tildes). Escribe `salir` para terminar.

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
- Depende de un servicio externo: si se superan los límites del nivel gratuito de Gemini, hay que esperar.

## 🔮 Próximos pasos

- [ ] 💻 **Agente de IT**: abrir y consultar tickets (la tabla `tickets` ya existe en la base de datos)
- [ ] Comparar con un modelo local más grande (`qwen2.5:14b`) para no depender de la nube
- [ ] Festivos en el cálculo de días laborables
- [ ] Memoria persistente (checkpointer en SQLite)
- [ ] API con FastAPI e interfaz con Streamlit

## 🛠️ Tecnologías

Python · LangChain · LangGraph · Gemini · Ollama (embeddinggemma) · Chroma · SQLite · Pydantic
