import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { PeticionChat, RespuestaChat } from '../interfaces/chat';

@Injectable({
  providedIn: 'root'
})
export class Chat {
  private http = inject(HttpClient);
  private url = 'http://localhost:8000/chat'; //Dirección del endPoint

  enviarMensaje(mensaje: string): Observable<RespuestaChat> {
    const peticion: PeticionChat = { mensaje:  mensaje}; //Creamos el json para enviar
    return this.http.post<RespuestaChat>(this.url, peticion); //Hace el POST a la API y devuelve el Observable
  }
}