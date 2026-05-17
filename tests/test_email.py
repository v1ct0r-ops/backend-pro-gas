"""
Tests unitarios — email_service.py

Cubre: _fmt_clp (función pura), _construir_html_reporte (función pura),
       enviar_resumen_cierre (guard SMTP, envío exitoso, error SMTP),
       enviar_reporte_diario (guard API key, envío exitoso, error Resend).
Sin conexión a BD ni a servicios externos — todo mockeado.
"""
from unittest.mock import MagicMock, patch


# ===========================================================================
# TEST SUITE 1: _fmt_clp — formateador de pesos chilenos
# ===========================================================================

class TestFmtClp:

    def test_formato_miles(self):
        from app.services.email_service import _fmt_clp
        assert _fmt_clp(1_250_000) == "$ 1.250.000"

    def test_formato_cero(self):
        from app.services.email_service import _fmt_clp
        assert _fmt_clp(0) == "$ 0"

    def test_formato_sin_miles(self):
        from app.services.email_service import _fmt_clp
        assert _fmt_clp(500) == "$ 500"


# ===========================================================================
# TEST SUITE 2: _construir_html_reporte — constructor de HTML (función pura)
# ===========================================================================

class TestConstruirHtmlReporte:

    def _base_kwargs(self, faltantes=None):
        return dict(
            fecha_str="16 de mayo de 2026",
            total_ventas=150_000,
            kilos_movidos=88.5,
            total_cierres=3,
            cerrados=2,
            pendientes=1,
            faltantes_detalle=faltantes or [],
        )

    def test_sin_faltantes_muestra_seccion_ok(self):
        from app.services.email_service import _construir_html_reporte

        html = _construir_html_reporte(**self._base_kwargs())

        assert "Sin alertas" in html
        assert "todos los cierres cuadran" in html

    def test_con_faltantes_muestra_tabla_de_alertas(self):
        from app.services.email_service import _construir_html_reporte

        html = _construir_html_reporte(
            **self._base_kwargs(faltantes=[("Carlos Soto", 5_000), ("Pedro Díaz", 3_000)])
        )

        assert "FALTANTE" in html
        assert "Carlos Soto" in html
        assert "Pedro Díaz" in html

    def test_html_contiene_datos_de_operacion(self):
        from app.services.email_service import _construir_html_reporte

        html = _construir_html_reporte(**self._base_kwargs())

        assert "16 de mayo de 2026" in html
        assert "88" in html  # kilos_movidos truncado en formato


# ===========================================================================
# TEST SUITE 3: enviar_resumen_cierre
# ===========================================================================

_KWARGS_CIERRE = dict(
    cierre_id=1,
    chofer_nombre="Carlos Soto",
    fecha="16/05/2026 09:00",
    total_ventas_calc=10_000,
    efectivo_rendido=8_000,
    vouchers_transbank=0,
    descuentos=2_000,
    diferencia=0,
    estado_cuadre="exacto",
)


class TestEnviarResumenCierre:

    def test_sin_smtp_configurado_no_envia(self):
        """Si SMTP_HOST está vacío, debe retornar sin enviar nada."""
        from app.services.email_service import enviar_resumen_cierre

        with patch("app.services.email_service.settings") as mock_cfg:
            mock_cfg.SMTP_HOST = ""
            mock_cfg.SMTP_USER = "user@test.com"
            mock_cfg.SUPER_ADMIN_EMAIL = "admin@test.com"

            with patch("smtplib.SMTP") as mock_smtp:
                enviar_resumen_cierre(**_KWARGS_CIERRE)
                mock_smtp.assert_not_called()

    def test_smtp_configurado_envia_email(self):
        """Con SMTP configurado, debe abrir la conexión y llamar sendmail."""
        from app.services.email_service import enviar_resumen_cierre

        with patch("app.services.email_service.settings") as mock_cfg:
            mock_cfg.SMTP_HOST = "smtp.test.com"
            mock_cfg.SMTP_USER = "noreply@progas.cl"
            mock_cfg.SUPER_ADMIN_EMAIL = "admin@progas.cl"
            mock_cfg.SMTP_PORT = 587
            mock_cfg.SMTP_PASSWORD = "secreto"
            mock_cfg.SMTP_FROM = None

            with patch("smtplib.SMTP") as MockSMTP:
                smtp_instance = MagicMock()
                MockSMTP.return_value.__enter__.return_value = smtp_instance

                enviar_resumen_cierre(**_KWARGS_CIERRE)

                smtp_instance.sendmail.assert_called_once()

    def test_smtp_error_no_propaga_excepcion(self):
        """Si el envío SMTP falla, el error debe loguearse pero NO propagarse."""
        from app.services.email_service import enviar_resumen_cierre

        with patch("app.services.email_service.settings") as mock_cfg:
            mock_cfg.SMTP_HOST = "smtp.test.com"
            mock_cfg.SMTP_USER = "noreply@progas.cl"
            mock_cfg.SUPER_ADMIN_EMAIL = "admin@progas.cl"
            mock_cfg.SMTP_PORT = 587
            mock_cfg.SMTP_PASSWORD = "secreto"
            mock_cfg.SMTP_FROM = None

            with patch("smtplib.SMTP", side_effect=ConnectionRefusedError("no hay conexión")):
                # No debe lanzar excepción — la función captura y loguea
                enviar_resumen_cierre(**_KWARGS_CIERRE)


# ===========================================================================
# TEST SUITE 4: enviar_reporte_diario
# ===========================================================================

def _make_db_reporte() -> MagicMock:
    """Mock de Session con las tres queries del reporte diario."""
    db = MagicMock()

    ventas_row = MagicMock()
    ventas_row.total_ventas = 200_000
    ventas_row.kilos = 110.0

    cierres_row = MagicMock()
    cierres_row.total = 3
    cierres_row.cerrados = 2
    cierres_row.pendientes = 1

    faltante_row = MagicMock()
    faltante_row.chofer_nombre = "Pedro Test"
    faltante_row.diferencia = 5_000

    # Primera .one() → ventas; segunda .one() → cierres; .all() → faltantes
    db.query.return_value.filter.return_value.one.side_effect = [ventas_row, cierres_row]
    db.query.return_value.filter.return_value.all.return_value = [faltante_row]

    return db


class TestEnviarReporteDiario:

    def test_sin_api_key_no_envia(self):
        """Si RESEND_API_KEY no está configurada, debe retornar sin enviar."""
        from app.services.email_service import enviar_reporte_diario

        with patch("app.services.email_service.settings") as mock_cfg:
            mock_cfg.RESEND_API_KEY = None

            with patch("resend.Emails.send") as mock_send:
                enviar_reporte_diario(db=MagicMock(), email_destino="admin@test.com")
                mock_send.assert_not_called()

    def test_con_api_key_llama_resend(self):
        """Con RESEND_API_KEY configurada, debe llamar resend.Emails.send."""
        from app.services.email_service import enviar_reporte_diario

        with patch("app.services.email_service.settings") as mock_cfg:
            mock_cfg.RESEND_API_KEY = "re_test_key_123"

            with patch("resend.Emails.send") as mock_send:
                enviar_reporte_diario(db=_make_db_reporte(), email_destino="admin@test.com")
                mock_send.assert_called_once()

    def test_error_resend_no_propaga_excepcion(self):
        """Si Resend falla, el error debe loguearse pero NO propagarse."""
        from app.services.email_service import enviar_reporte_diario

        with patch("app.services.email_service.settings") as mock_cfg:
            mock_cfg.RESEND_API_KEY = "re_test_key_123"

            with patch("resend.Emails.send", side_effect=Exception("timeout Resend")):
                # No debe lanzar — la función captura y loguea
                enviar_reporte_diario(db=_make_db_reporte(), email_destino="admin@test.com")
