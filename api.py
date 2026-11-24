from fastapi import FastAPI
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from fastapi.middleware.cors import CORSMiddleware
from app import app_orquestador

api = FastAPI()

api.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],    # solo tu Angular puede llamar a la API
    allow_methods=["*"],                        # cualquier método: GET, POST...
    allow_headers=["*"],                        # cualquier cabecera (por ejemplo, Content-Type)
)

CONFIG = {"configurable": {"thread_id": "web-lucia", "empleado_id": 1}}

class PeticionChat(BaseModel):
    mensaje: str

class RespuestaChat(BaseModel):
    respuesta: str
    especialistas: list[str]
    
    
@api.post("/chat", response_model=RespuestaChat)
def chat(peticion: PeticionChat):

    resultado = app_orquestador.invoke({"messages": [HumanMessage(peticion.mensaje)]}, config=CONFIG)

    mensajes = resultado["messages"]

    # 2. Posición del último mensaje del empleado: ahí empieza esta pregunta
    inicio = max(i for i, m in enumerate(mensajes) if isinstance(m, HumanMessage))

    # 3. Apuntamos a qué especialistas ha consultado en esta pregunta, sin repetidos
    especialistas = []
    for m in mensajes[inicio:]:
        if getattr(m, "tool_calls", None):
            for llamada in m.tool_calls:
                if llamada["name"] not in especialistas:
                    especialistas.append(llamada["name"])

    return RespuestaChat(respuesta=mensajes[-1].text, especialistas=especialistas)
    
    