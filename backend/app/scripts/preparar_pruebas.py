"""Prepara únicamente la instalación efímera definida en compose.pruebas.yml."""
import asyncio
from app.core.config import settings
from app.core.db import get_db, close_connections
from app.migrations import runner
from app.services import demo_service


async def main():
    if settings.app_env != 'test' or settings.mongo_db != 'helpdesk_test_navegador':
        raise RuntimeError('Solo se admite la instalación aislada de navegador.')
    try:
        await runner.ejecutar()
        if not await get_db().usuarios.count_documents({}):
            await demo_service.cargar()
        print('Instalación ficticia de navegador preparada.')
    finally:
        await close_connections()


if __name__ == '__main__':
    asyncio.run(main())
