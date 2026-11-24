// Lo que se envía a la API (POST /chat)
export interface PeticionChat {
  mensaje: string;
}

// Lo que devuelve la API
export interface RespuestaChat {
  respuesta: string;
  especialistas: string[];
}

// Cada burbuja del chat
export interface Mensaje {
  autor: 'empleado' | 'asistente';
  texto: string;
  especialistas?: string[];
}
