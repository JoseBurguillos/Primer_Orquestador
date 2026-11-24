import sqlite3                                                      # base de datos (vacaciones y tickets)

from langchain_core.tools import tool                               # convertir funciones en herramientas
from langchain_core.messages import HumanMessage, SystemMessage     # mensajes del cliente y prompt del sistema
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import OllamaEmbeddings                       # el modelo que piensa + el de embeddings
from langchain_chroma import Chroma                                 # base vectorial (normativa)
from langchain_ollama import OllamaEmbeddings                       # el modelo que piensa + el de embeddings
from dotenv import load_dotenv

from langgraph.graph import StateGraph, START, END, MessagesState   # el grafo
from langgraph.prebuilt import ToolNode                             # nodo que ejecuta las herramientas
from langgraph.checkpoint.memory import MemorySaver                 # memoria de la conversación
from langchain_core.runnables import RunnableConfig                 # datos que pasa el programa, no el modelo
from datetime import date, timedelta

load_dotenv()

modelo = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite", temperature=0)

embeddings = OllamaEmbeddings(model="embeddinggemma") 

base_vectorial=Chroma( 
    collection_name="normativa",
    embedding_function=embeddings,
    persist_directory="./base_chroma"
)

ruta_bd="empresa.db"

PROMPT_NORMATIVA = """Eres el asistente de normativa interna de Nubaria Tech. Respondes a los empleados sobre las normas y políticas de la empresa: vacaciones y permisos, teletrabajo, gastos y viajes, soporte informático y bienvenida a nuevos empleados. Respondes siempre en español, de forma clara y breve.

Reglas:
- Responde SOLO con la información del apartado "Normativa encontrada". No uses conocimientos generales ni lo que hagan otras empresas.
- Si la información no aparece en ese apartado, di que no la encuentras en la normativa y recomienda contactar con el departamento correspondiente. No te la inventes.
- Si la normativa dice que algo NO está permitido o NO existe, díselo claramente al empleado.
- Cuando sea útil, indica de qué documento sale la información (por ejemplo, "según la política de teletrabajo...").
- Da datos concretos (días, plazos, importes) tal y como aparecen en la normativa.
- Responde solo a lo que se pregunta. No añadas requisitos, pasos, condiciones ni consejos que no aparezcan escritos en la normativa para ese caso concreto.
"""


def buscar_normativa(pregunta:str)->str: #busca los fragmentos que tienen similitud a la pregunta
    
    """Busca en la normativa interna de Nubaria Tech la información relacionada con la pregunta del empleado.
    Úsala para cualquier duda sobre las normas y políticas de la empresa: vacaciones y permisos,
    teletrabajo, gastos y viajes, soporte informático (cómo abrir tickets, contraseñas, VPN...)
    y bienvenida a nuevos empleados (horario, oficina, beneficios...).
    Recibe la pregunta del empleado y devuelve los fragmentos de la normativa más relacionados,
    indicando de qué documento sale cada uno."""
    
    fragmentos=base_vectorial.similarity_search( #buscamos los que tienen sentido
        pregunta,k=4 #Nos dara 4
    )
    
    textos=[] #almacenamos aqui los fragmentos
    for fragmento in fragmentos: #recorremos los que nos ha dado
        textos.append(f"[{fragmento.metadata['fuente']}]\n{fragmento.page_content}")
        
    return "\n\n".join(textos)
        
    
    
def nodo_normativa(state:MessagesState):
    #"cerebro" del agente: decide si buscar en la normativa o responder
    pregunta = state["messages"][-1].content    # el TEXTO del último mensaje
    contexto = buscar_normativa(pregunta)
    
    sistema = f"{PROMPT_NORMATIVA}\n\nNormativa encontrada:\n{contexto}"
    
    respuesta = modelo.invoke([SystemMessage(sistema)] + state["messages"])
    
    return {"messages":[respuesta]} # añade la respuesta (texto o petición de herramienta) a la conversación



def decidir(state:MessagesState):
    ultimo=state['messages'][-1] #coge el ultimo mensaje
    if ultimo.tool_calls: #comprobamos si ha pedido alguna herramienta
        return "tools"
    
    return END


grafo_normativa=StateGraph(MessagesState)

grafo_normativa.add_node("agente",nodo_normativa)

grafo_normativa.add_edge(START,"agente")
grafo_normativa.add_edge("agente",END)

app_normativa=grafo_normativa.compile()


@tool
def consultar_dias(config:RunnableConfig) -> str:
    
    """Consulta cuántos días de vacaciones le quedan al empleado que está hablando."""
    empleado_id = config["configurable"]["empleado_id"]     # lo pone el programa, no el modelo
    conexion=sqlite3.connect("empresa.db")
    cursor=conexion.cursor()
    cursor.execute("SELECT nombre, dias_vacaciones FROM empleados WHERE id = ?", 
                   (empleado_id,))
    fila = cursor.fetchone()
    
    if fila is None:
        conexion.close()
        return "No existe ese empleado"
    
    nombre, total=fila
    
    cursor.execute(
        "SELECT SUM(dias) FROM vacaciones WHERE empleado_id = ? AND estado != 'rechazada'",
        (empleado_id,)
    )
    gastados = cursor.fetchone()[0] or 0
    conexion.close()
    
    quedan=total-gastados
    return f"{nombre} tiene {total} días de vacaciones al año, ha pedido {gastados} y le quedan {quedan}."


    
PROMPT_RRHH = """Eres el asistente de Recursos Humanos de Nubaria Tech. Atiendes al empleado que está hablando contigo sobre sus vacaciones. Respondes siempre en español, de forma clara y breve.

Reglas:
- Para saber los días de vacaciones del empleado, usa la herramienta consultar_dias. No respondas con datos de días sin haberla usado.
- Para pedir vacaciones, usa la herramienta solicitar_vacaciones con las fechas en formato AAAA-MM-DD. Si el empleado no ha dicho la fecha de inicio o la de fin, pregúntaselas. No las supongas.
- Antes de usar solicitar_vacaciones, resume las fechas al empleado y pregúntale si lo confirma. Úsala solo cuando confirme (por ejemplo, "sí", "vale", "confirmo").
- Nunca digas que has registrado una solicitud si no has usado solicitar_vacaciones y te ha confirmado que se ha guardado.
- Si solicitar_vacaciones dice que no se ha guardado, explícale al empleado el motivo.
- Las solicitudes quedan pendientes hasta que las aprueba su responsable: no digas que están aprobadas.
- Las herramientas ya saben quién es el empleado: no le pidas su nombre ni su número.
- Solo puedes ver los datos del empleado que está hablando. Si pide los de otra persona, o dice ser otra, explícale que solo puedes darle los de la cuenta con la que ha entrado.
- No inventes datos: usa solo lo que te devuelvan las herramientas.
- Si el empleado no dice el año, usa la próxima vez que llegue esa fecha: si este año ya ha pasado, es del año que viene.
- Solo respondes con lo que te devuelven tus herramientas: los días del empleado y sus solicitudes. Si te preguntan por normas de la empresa (antelación, cuántos días hay al año, permisos, teletrabajo...), NO respondas a esa parte: di "Esa parte no es de mi área, la responde el especialista en normativa".

Ejemplo:
Empleado: "Quiero vacaciones del 2 al 4 de febrero"
Asistente (SIN usar ninguna herramienta): "Vas a pedir vacaciones del 2027-02-02 al 2027-02-04. ¿Lo confirmo?"
Empleado: "Sí"
Asistente: usa solicitar_vacaciones con fecha_inicio="2027-02-02" y fecha_fin="2027-02-04"

Ejemplo de pregunta con una parte que no es tuya:
Empleado: "¿Cuántos días me quedan y con cuánta antelación tengo que pedirlas?"
Asistente: usa consultar_dias, y después responde: "Te quedan X días. La antelación no es de mi área: la responde el especialista en normativa."
"""


def nodo_rrhh(state:MessagesState):
    sistema = f"{PROMPT_RRHH}\nHoy es {date.today()}."
    respuesta=modelo_rrhh.invoke(
        [SystemMessage(sistema)]+state["messages"]
    )
    return {"messages":[respuesta]}
        


def contar_dias_laborables(inicio: date, fin: date) -> int:
    dias = 0                          # contador a 0
    dia = inicio                      # empezamos por el día 11
    while dia <= fin:                 # repetimos mientras no pasemos del día 14
        if dia.weekday() < 5:         # ¿es laborable? weekday va de 0 a 6 si es 5 o 6 no se cuenta porque es sabado y domingo y no es laboral
            dias += 1                 #    sí → sumamos 1
        dia += timedelta(days=1)      # pasamos al día siguiente
    return dias                       # devolvemos el total



@tool
def solicitar_vacaciones(fecha_inicio:str,fecha_fin:str,config: RunnableConfig)->str:
    """Registra una solicitud de vacaciones del empleado que está hablando.
    Úsala cuando el empleado quiera pedir o reservar días de vacaciones y ya haya dicho
    la fecha de inicio y la fecha de fin.
    Las dos fechas deben ir en formato AAAA-MM-DD (por ejemplo, 2026-12-11).
    La fecha de fin es el último día de vacaciones, incluido.
    Devuelve si la solicitud se ha guardado o el motivo por el que no se ha podido guardar.
    La solicitud queda pendiente hasta que la apruebe su responsable."""
    
    inicio = date.fromisoformat(fecha_inicio)
    fin = date.fromisoformat(fecha_fin)
    
    if fin < inicio:
        return "No se ha guardado: la fecha de fin no puede ser anterior a la fecha de inicio."

    antelacion = (inicio - date.today()).days
    if antelacion < 15:
        return f"No se ha guardado: las vacaciones se piden con al menos 15 días de antelación y faltan {antelacion} días para la fecha de inicio."

    
    dias_pedidos=contar_dias_laborables(inicio,fin)
    
    if dias_pedidos == 0:
        return "No se ha guardado: entre esas fechas no hay ningún día laborable."
        
    
    empleado_id=config["configurable"]["empleado_id"]
    
    conexion=sqlite3.connect("empresa.db")
    cursor=conexion.cursor()
    cursor.execute("SELECT nombre, dias_vacaciones FROM empleados WHERE id=?",
                   (empleado_id,))
    fila=cursor.fetchone()
    
    
    if fila is None:
        conexion.close()
        return "No existe ese empleado"
    
    total=fila[1]
    
    cursor.execute("SELECT SUM(dias) FROM vacaciones WHERE empleado_id=? AND estado != 'rechazada'",
                    (empleado_id,))
    gastados = cursor.fetchone()[0] or 0
    quedan = total - gastados
    
    
    if dias_pedidos <= quedan:
        cursor.execute("INSERT INTO vacaciones (empleado_id,fecha_inicio,fecha_fin,dias) VALUES (?,?,?,?)",
                       (empleado_id,fecha_inicio,fecha_fin,dias_pedidos,))
        conexion.commit()
        cursor.close()
        conexion.close()
        return f"{fila[0]}, se ha guardado la solicitud de vacaciones, has pedido {dias_pedidos} y queda pendiente "
    else:
        cursor.close()
        conexion.close()
        return f"No te quedan tantos días, te quedan {quedan}"    

    
    
herramientas=[consultar_dias,solicitar_vacaciones]
modelo_rrhh=modelo.bind_tools(herramientas)    
    
grafo_rrhh=StateGraph(MessagesState)

grafo_rrhh.add_node("agente",nodo_rrhh)
grafo_rrhh.add_node("tools", ToolNode(herramientas))

grafo_rrhh.add_edge(START, "agente")
grafo_rrhh.add_conditional_edges("agente",decidir)
grafo_rrhh.add_edge("tools", "agente")

app_rrhh = grafo_rrhh.compile(checkpointer=MemorySaver())


def identificar_empleado(nombre: str):
    conexion=sqlite3.connect("empresa.db")
    cursor=conexion.cursor()
    cursor.execute("SELECT id FROM empleados WHERE nombre=? COLLATE NOCASE",
                   (nombre,))
    fila = cursor.fetchone()
    conexion.close()
    if fila is None:
        return None
    return fila[0]


@tool
def consultar_incidencia(config:RunnableConfig)->str:
    """Consulta los tickets de soporte informático del empleado que está hablando.
    Úsala cuando el empleado pregunte por sus incidencias o tickets: cuáles tiene abiertos,
    cómo va uno en concreto o si ya se ha resuelto.
    Devuelve la lista de sus tickets con el número (por ejemplo, T001), el título,
    la prioridad, el estado (abierto, en curso o resuelto) y la fecha."""
    identificador=config["configurable"]["empleado_id"]
    
    conexion=sqlite3.connect("empresa.db")
    cursor=conexion.cursor()
    cursor.execute("SELECT id,titulo,prioridad,estado,fecha from tickets WHERE empleado_id=?",
                   (identificador,))
    filas=cursor.fetchall()
    conexion.close()
    
    if not filas:
        return "No tienes tickets todavia"
    
    lineas=[]
    
    for id_ticket,titulo,prioridad,estado,fecha in filas:
        lineas.append(f"T{id_ticket}-{titulo}-prioridad:{prioridad}-{estado}-{fecha}")
        
    return "\n".join(lineas)



@tool
def crear_incidencia(titulo: str|None, descripcion: str|None, prioridad: str|None, config: RunnableConfig)->str:
    """Abre un ticket de soporte informático para el empleado que está hablando.
    Úsala cuando el empleado tenga un problema informático (el portátil, la VPN, una contraseña,
    un programa...) y ya haya explicado qué le pasa.
    - titulo: resumen corto del problema (por ejemplo, "No funciona la VPN").
    - descripcion: qué le pasa, explicado con las palabras del empleado.
    - prioridad: una de estas cuatro, en minúsculas:
        "critica": impide trabajar a varias personas, afecta a clientes, o se ha perdido o robado un equipo.
        "alta": impide trabajar al empleado.
        "media": molesta, pero puede seguir trabajando.
        "baja": peticiones y consultas, como instalar un programa.
    Devuelve el número del ticket creado o el motivo por el que no se ha podido crear."""
    
    identificador=config["configurable"]["empleado_id"]
    fecha = date.today().isoformat()
    
    if titulo is None:
        return "Titulo esta vacio"
    if descripcion is None:
        return "Descripcion esta vacio"    
    if prioridad is None:
        return "Prioridad esta vacio"
    if prioridad not in ["critica", "alta", "media", "baja"]:
        return "No se ha creado el ticket: la prioridad tiene que ser critica, alta, media o baja."        
    
    conexion=sqlite3.connect("empresa.db")
    cursor=conexion.cursor()
    
    cursor.execute("INSERT INTO tickets (empleado_id,titulo, descripcion,prioridad,fecha) VALUES(?,?,?,?,?)",
                   (identificador,titulo,descripcion,prioridad,fecha,))
    
    conexion.commit()
    nuevo_id = cursor.lastrowid          # el id que ha puesto SQLite (por ejemplo, 4)
    conexion.close()
    
    return f"Ticket T{nuevo_id:03d} creado con prioridad {prioridad}. Estado: abierto."

PROMPT_INCIDENCIAS = """Eres el asistente de soporte informático (IT) de Nubaria Tech. Atiendes al empleado que está hablando contigo sobre sus incidencias informáticas. Respondes siempre en español, de tú, de forma clara y breve.

Reglas:
- Para saber qué tickets tiene el empleado y cómo van, usa la herramienta consultar_incidencia. No respondas sobre sus tickets sin haberla usado.
- Para abrir un ticket, usa la herramienta crear_incidencia. Necesitas saber qué le pasa al empleado. Si no lo ha explicado, pregúntaselo. No te lo inventes.
- Elige tú la prioridad según el problema: "critica" si impide trabajar a varias personas, afecta a clientes o se ha perdido o robado un equipo; "alta" si le impide trabajar a él; "media" si molesta pero puede seguir trabajando; "baja" para peticiones y consultas.
- Antes de usar crear_incidencia, resume al empleado el título y la prioridad del ticket y pregúntale si lo abres. Úsala solo cuando confirme (por ejemplo, "sí", "vale").
- Nunca digas que has abierto un ticket si no has usado crear_incidencia y te ha devuelto su número.
- Cuando abras un ticket, dale al empleado su número (por ejemplo, T004).
- Solo respondes sobre los tickets del empleado. Si te preguntan por normas de la empresa (plazos, contraseñas, qué hacer si pierdes el portátil...), NO respondas a esa parte: di "Esa parte no es de mi área, la responde el especialista en normativa".
- Las herramientas ya saben quién es el empleado: no le pidas su nombre ni su número.
- No inventes datos: usa solo lo que te devuelvan las herramientas.

Ejemplo de cómo actuar:
Empleado: "No me funciona la impresora de la oficina"
Tú, SIN usar ninguna herramienta, respondes: "Voy a abrir un ticket 'No funciona la impresora' con prioridad media. ¿Lo abro?"
Empleado: "Sí"
Tú llamas a la herramienta crear_incidencia con titulo="No funciona la impresora", descripcion="No me funciona la impresora de la oficina", prioridad="media".
"""

herramientas_tickets=[consultar_incidencia,crear_incidencia]
modelo_ticket=modelo.bind_tools(herramientas_tickets)

def agente_tickets(state:MessagesState):
    sistema = f"{PROMPT_INCIDENCIAS}"
    respuesta=modelo_ticket.invoke(
        [SystemMessage(sistema)]+state["messages"]
    )
    return {"messages":[respuesta]}

grafo_tickets=StateGraph(MessagesState)
grafo_tickets.add_node("agente",agente_tickets)
grafo_tickets.add_node("tools",ToolNode(herramientas_tickets))

grafo_tickets.add_edge(START, "agente")
grafo_tickets.add_conditional_edges("agente",decidir)
grafo_tickets.add_edge("tools", "agente")

app_ticket=grafo_tickets.compile(MemorySaver())

# ==================== ORQUESTADOR ====================

@tool
def preguntar_normativa(pregunta:str)->str:
    """Consulta al especialista en normativa interna de Nubaria Tech.
    Úsala para dudas sobre las normas y políticas de la empresa, que son iguales para todos los empleados:
    vacaciones y permisos (cuántos días hay al año, antelación, permisos retribuidos), teletrabajo,
    gastos y viajes, soporte informático (cómo abrir tickets, contraseñas, VPN) y la guía de bienvenida
    (horario, oficina, parking, beneficios).
    NO sabe nada de los datos de cada empleado: para saber cuántos días de vacaciones le quedan
    o para pedir vacaciones, usa preguntar_rrhh.
    Recibe la pregunta del empleado, completa y en español, y devuelve la respuesta del especialista."""
    
    resultado=app_normativa.invoke({"messages":
        [HumanMessage(pregunta)]
    })
    
    return resultado["messages"][-1].content


@tool
def preguntar_rrhh(peticion: str, config: RunnableConfig) -> str:
    """Consulta al especialista de Recursos Humanos sobre las vacaciones del empleado que está hablando.
    Úsala para saber cuántos días de vacaciones le quedan, para pedir vacaciones y para
    confirmar una solicitud que el especialista haya preparado (cuando el empleado responde "sí", "vale"...).
    NO responde dudas sobre las normas de la empresa: para eso, usa preguntar_normativa.
    Recibe lo que ha dicho el empleado, completo y en español, y devuelve la respuesta del especialista."""

    config_rrhh = {"configurable": {
        "thread_id": config["configurable"]["thread_id"] + "-rrhh",
        "empleado_id": config["configurable"]["empleado_id"],
    }}
    
    resultado=app_rrhh.invoke({"messages":[HumanMessage(peticion)]},config=config_rrhh)
    return resultado["messages"][-1].content

@tool
def preguntar_tickets(peticion: str, config: RunnableConfig) -> str:
    """Consulta al especialista de soporte informático (IT) sobre las incidencias del empleado que está hablando.
    Úsala para abrir un ticket cuando el empleado tenga un problema informático (portátil, VPN, contraseña,
    programas...), para saber cómo van sus tickets y para confirmar un ticket que el especialista haya
    preparado (cuando el empleado responde "sí", "vale"...).
    NO responde dudas sobre las normas de la empresa: para eso, usa preguntar_normativa.
    Recibe lo que ha dicho el empleado, completo y en español, y devuelve la respuesta del especialista."""

    config_tickets = {"configurable": {
        "thread_id": config["configurable"]["thread_id"] + "-tickets",
        "empleado_id": config["configurable"]["empleado_id"],
    }}

    resultado = app_ticket.invoke({"messages": [HumanMessage(peticion)]}, config=config_tickets)
    return resultado["messages"][-1].content

PROMPT_ORQUESTADOR = """Eres el asistente interno de Nubaria Tech. Atiendes a los empleados en español, de tú, de forma clara y breve.
No respondes con lo que tú sabes: pasas cada petición al especialista que corresponde y le das al empleado su respuesta.

Especialistas:
- preguntar_normativa: dudas sobre las normas de la empresa, iguales para todos (vacaciones, permisos, teletrabajo, gastos y viajes, informática, oficina, beneficios).
- preguntar_rrhh: los datos y gestiones de vacaciones del empleado (cuántos días le quedan, pedir vacaciones, confirmar una solicitud).
- preguntar_tickets: las incidencias informáticas del empleado (abrir un ticket, saber cómo van sus tickets, confirmar un ticket).
Reglas:
- Para cualquier pregunta sobre la empresa o sobre los datos del empleado, usa SIEMPRE al especialista. No respondas de memoria.
- Pásale al especialista lo que ha dicho el empleado, completo, con las fechas y los datos que haya dado.
- Si la pregunta tiene varias partes de especialistas distintos, consulta a los dos antes de responder.
- Si un especialista hace una pregunta al empleado (por ejemplo, "¿Lo confirmo?"), transmítesela tal cual. Cuando el empleado responda, pásale la respuesta a ESE MISMO especialista.
- No cambies los datos que te den los especialistas (días, fechas, importes, plazos).
- Solo puedes responder sin especialista a saludos y despedidas. Si te preguntan algo que no tiene que ver con la empresa, di que solo puedes ayudar con temas de Nubaria Tech.

A quién consultar (esto NO es lo que tienes que escribir: es la herramienta que tienes que llamar):
- "¿Cuántos días puedo teletrabajar?" → llamar a la herramienta preguntar_normativa
- "¿Cuántos días de vacaciones me quedan?" → llamar a la herramienta preguntar_rrhh
- "¿Cuántos días me quedan y con cuánta antelación tengo que pedirlas?" → llamar a preguntar_rrhh y también a preguntar_normativa
- "Sí" justo después de que RRHH haya preguntado "¿Lo confirmo?" → llamar a preguntar_rrhh con "Sí, lo confirmo"
- Nunca escribas al empleado el nombre de una herramienta: llámala.
- Si un especialista dice que una parte no es de su área, pregunta esa parte al otro especialista antes de responder.
- "No me funciona la VPN" → llamar a la herramienta preguntar_tickets
- "¿Cómo va mi ticket?" → llamar a la herramienta preguntar_tickets
- "He perdido el portátil, ¿qué tengo que hacer?" → llamar a preguntar_normativa (qué dice la norma) y también a preguntar_tickets (abrir el ticket)
- "Sí" justo después de que IT haya preguntado "¿Lo abro?" → llamar a preguntar_tickets con "Sí, ábrelo"
"""
herramientas_orquestador=[preguntar_normativa,preguntar_rrhh,preguntar_tickets]
modelo_orquestador=modelo.bind_tools(herramientas_orquestador)

def nodo_orquestador(state:MessagesState):
    sistema = f"{PROMPT_ORQUESTADOR}\nHoy es {date.today()}."
    respuesta=modelo_orquestador.invoke(
        [SystemMessage(sistema)]+state["messages"]
    )
    return {"messages":[respuesta]}

grafo_orquestador=StateGraph(MessagesState)

grafo_orquestador.add_node("node_orquestador", nodo_orquestador)
grafo_orquestador.add_node("tools", ToolNode(herramientas_orquestador))

grafo_orquestador.add_edge(START,"node_orquestador")
grafo_orquestador.add_conditional_edges("node_orquestador",decidir)
grafo_orquestador.add_edge("tools","node_orquestador")

app_orquestador = grafo_orquestador.compile(checkpointer=MemorySaver())



if __name__ == "__main__":
    nombre = input("¿Cómo te llamas? ")
    empleado_id = identificar_empleado(nombre)

    if empleado_id is None:
        print("No hay ningún empleado con ese nombre.")
        exit()

    config = {"configurable": {"thread_id": f"empleado-{empleado_id}", "empleado_id": empleado_id}}
    print(f"¡Hola, {nombre}! ¿En qué te puedo ayudar? (escribe 'salir' para terminar)")

    while True:
        pregunta = input("\nTú: ")
        if pregunta == "salir":
            break
        resultado = app_orquestador.invoke({"messages": [HumanMessage(pregunta)]}, config=config)
        for m in resultado["messages"][-6:]:
            if getattr(m, "tool_calls", None):
                for llamada in m.tool_calls:
                    print("", llamada["name"], ":", llamada["args"])
        print("Asistente:", resultado["messages"][-1].content)