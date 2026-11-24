import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Chat as ChatService } from '../../services/chat';   // alias: el componente también se llama Chat
import { Mensaje } from '../../interfaces/chat';

@Component({
  selector: 'app-chat',
  imports: [FormsModule],          // para usar [(ngModel)] en la caja de texto
  templateUrl: './chat.html',
  styleUrl: './chat.css'
})
export class Chat {
  private chatService = inject(ChatService);

  mensajes = signal<Mensaje[]>([]);   // la conversación
  texto = '';                         // lo que está escribiendo el usuario
  cargando = signal(false);           // true mientras espera la respuesta de la API

  enviar() {
    const pregunta = this.texto.trim();
    if (!pregunta || this.cargando()) return;   // no enviar vacío, ni otro mensaje mientras espera

      // Añadimos el mensaje del empleado y vaciamos la caja de texto
      this.mensajes.update(lista => [...lista, { autor: 'empleado', texto: pregunta }]);
      this.texto = '';
      this.cargando.set(true);

      // Llamamos a la API (la petición sale al hacer subscribe)
      this.chatService.enviarMensaje(pregunta).subscribe({
        // La API ha respondido: añadimos la respuesta del asistente
        next: (respuesta) => {
          this.mensajes.update(lista => [...lista, {
            autor: 'asistente',
            texto: respuesta.respuesta,
            especialistas: respuesta.especialistas
          }]);
          this.cargando.set(false);
        },
      //Algo ha fallado avisamos en el chat
      error: () => {
        this.mensajes.update(lista => [...lista, {
          autor: 'asistente',
          texto: 'No he podido conectar con el asistente. ¿Está la API en marcha?'
        }]);
        this.cargando.set(false);
      }
    });
  }
}