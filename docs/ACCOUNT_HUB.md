# Account Hub

Estados de conexiÃ³n: `not_configured`, `pending_authorization`, `connected`, `expired`, `revoked`, `error`.

## Ciclo de vida implementado
- `register_connection(service, tipo, scopes, secret_ref=None)` â `pending_authorization` (siempre sin autorizar; si ya existÃ­a, se reinicia).
- `grant(service)` â `connected`. Solo desde `pending_authorization`: es el punto donde la UI registrarÃ¡ el consentimiento tras un flujo oficial.
- `mark_expired` (solo desde `connected`), `mark_error`, `revoke` â `revoked`. Una conexiÃ³n revocada no puede volver a autorizarse sin volver a registrarla.
- `may_access(service, scope)`: verdadero solo si estÃ¡ `connected` y el scope fue declarado.

## MÃ©todos de conexiÃ³n previstos
- OAuth/API oficial.
- Conector local documentado con consentimiento explÃ­cito.
- ImportaciÃ³n manual de configuraciÃ³n no secreta.

## Secretos
No se almacenan contraseÃ±as en texto plano ni en el Hub. Los secretos van en `nexora.core.vault` (RAM por defecto; almacÃ©n del SO con `keyring`) y el Hub guarda solo la referencia. Beta 0.2 incluye contratos y ciclo de vida, **no integraciones reales**.
