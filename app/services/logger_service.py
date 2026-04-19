from datetime import datetime

from sqlalchemy.orm import Session

from app.models.models import BitacoraLlamada
from app.schemas.bitacora import BitacoraCreate


def registrar_llamada(db: Session, payload: BitacoraCreate, usuario_id: int) -> BitacoraLlamada:
    entrada = BitacoraLlamada(
        cliente_nombre=payload.cliente_nombre,
        telefono=payload.telefono,
        direccion=payload.direccion,
        detalle_pedido=payload.detalle_pedido,
        fecha_hora=datetime.utcnow(),
        usuario_id=usuario_id,
    )
    db.add(entrada)
    db.commit()
    db.refresh(entrada)
    return entrada
