"""
Tests unitarios — logger_service.py (registrar_llamada)
Sin conexión a BD — todo vía MagicMock.
"""
from unittest.mock import MagicMock


class TestRegistrarLlamada:

    def test_registrar_llamada_persiste_y_retorna(self):
        """registrar_llamada debe hacer add, commit, refresh y retornar el objeto."""
        from app.services.logger_service import registrar_llamada

        payload = MagicMock()
        payload.cliente_nombre = "Juan Test"
        payload.telefono = "999888777"
        payload.direccion = "Av. Test 123"
        payload.detalle_pedido = "2 cilindros 11kg"

        db = MagicMock()

        resultado = registrar_llamada(db, payload, usuario_id=5)

        db.add.assert_called_once()
        db.commit.assert_called_once()
        db.refresh.assert_called_once()

    def test_registrar_llamada_usa_datos_del_payload(self):
        """Los campos del payload deben pasarse al modelo BitacoraLlamada."""
        from app.services.logger_service import registrar_llamada

        payload = MagicMock()
        payload.cliente_nombre = "María López"
        payload.telefono = "987654321"
        payload.direccion = "Calle Principal 456"
        payload.detalle_pedido = "1 cilindro 5kg"

        db = MagicMock()
        registrar_llamada(db, payload, usuario_id=3)

        # Verificar que db.add fue llamado con un objeto que tiene los campos correctos
        args, _ = db.add.call_args
        entrada = args[0]
        assert entrada.cliente_nombre == "María López"
        assert entrada.telefono == "987654321"
        assert entrada.direccion == "Calle Principal 456"
        assert entrada.detalle_pedido == "1 cilindro 5kg"
        assert entrada.usuario_id == 3
