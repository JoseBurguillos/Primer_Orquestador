import os                                                            # recorrer la carpeta documentos/
import hashlib                                                       # IDs SHA-256 (evitar duplicados)

from langchain_core.documents import Document                       # el "objeto documento": texto + metadata
from langchain_text_splitters import RecursiveCharacterTextSplitter # partir en fragmentos
from langchain_ollama import OllamaEmbeddings                       # texto → vector
from langchain_chroma import Chroma                                 # base vectorial


archivos=os.listdir("documentos") #leemos las rutas de todos los archivos de documentos

documentos=[] #Guardamos los documentos aqui

for archivo in archivos:
    if not archivo.endswith(".txt"): #filtramos todos lo que no sean .txt
        continue
    
    ruta=os.path.join("documentos", archivo)#Unimos la carpeta y el nombre del archivo para las rutas (poder consultar el archivo al tner la ruta)
    
    with open(ruta, encoding="utf-8") as f: #abrimos las rutas, y leemos el archivo
        texto=f.read() #Leemos el texto
        documentos.append( #Añadimos a documentos un objeto documento con su texto y su ruta en los metadatos
            Document(page_content=texto, 
                metadata={
                    "fuente":archivo
                })
    )
    
print(len(documentos))
    
divisor=RecursiveCharacterTextSplitter( #Creamos el divisor de los archivos
    chunk_size=500,
    chunk_overlap=100
)

fragmentos=divisor.split_documents(documentos) #fragmentamos todos los documentos 

ids=[] #Creamos los ids de los fragmentos para guardarlos en chroma

for fragmento in fragmentos:
    texto=f"{fragmento.metadata["fuente"]}{fragmento.page_content}" #unimos la ruta y el contenido de cada uno, así tenemos un id distinto cada vez
    textobyte=texto.encode("utf-8") #Pasamos el texto a bytes
    generador_hash=hashlib.sha256(textobyte) #Lo hasheamos para luego pasarlo a id
    identificador=generador_hash.hexdigest() #propiedad para sacar el id del hash

    ids.append(identificador) #lo guardamos en la lista

embeddings = OllamaEmbeddings( #convierte el texto en vectores
    model="embeddinggemma"
)

base_vectorial=Chroma( #Para guardar los fragmentos con sus IDs
    collection_name="normativa",
    embedding_function=embeddings,
    persist_directory="./base_chroma"
)

base_vectorial.add_documents( #Añadimos todos los documetnos y sus IDS
    documents=fragmentos,
    ids=ids
)

datos= base_vectorial.get() #Los datos almacenados ahí
print("Guardados en Chroma:", len(datos["ids"]))





