from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import DependeUsuario, DependeUsuarioCsrf
from app.core.ratelimit import comprobar_limite
from app.services import chatbot_service, conversaciones_chatbot

router = APIRouter(tags=['Chatbot TI'])


class Mensaje(BaseModel):
    rol: Literal['user', 'assistant']
    texto: str = Field(min_length=1, max_length=12000)


class Consulta(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    pregunta: str = Field(min_length=2, max_length=1500)
    historial: list[Mensaje] = Field(default_factory=list, max_length=6)
    pagina: str | None = Field(default=None, max_length=180, pattern=r'^/(panel|portal)(/[^?#]*)?$')
    filtros: dict[str, str] = Field(default_factory=dict, max_length=15)
    conversacion_id: str | None = Field(default=None, max_length=24)


@router.get('/ia/chatbot/estado')
async def estado(sesion: DependeUsuario):
    return {**chatbot_service.estado(sesion.usuario), 'limite_consultas': conversaciones_chatbot.limite(sesion.usuario)}


@router.get('/ia/chatbot/conversaciones')
async def listar(sesion: DependeUsuario):
    return await conversaciones_chatbot.listar(sesion.usuario)


@router.get('/ia/chatbot/conversaciones/{conversacion_id}')
async def obtener(conversacion_id: str, sesion: DependeUsuario):
    return await conversaciones_chatbot.obtener(conversacion_id, sesion.usuario)


@router.delete('/ia/chatbot/conversaciones/{conversacion_id}')
async def eliminar(conversacion_id: str, sesion: DependeUsuarioCsrf):
    return await conversaciones_chatbot.eliminar(conversacion_id, sesion.usuario)


@router.post('/ia/chatbot')
async def consultar(datos: Consulta, sesion: DependeUsuarioCsrf):
    chatbot_service.exigir_ti(sesion.usuario)
    await comprobar_limite(f'chatbot:{sesion.id}', limite=10)
    return await conversaciones_chatbot.consultar(datos, sesion.usuario)
