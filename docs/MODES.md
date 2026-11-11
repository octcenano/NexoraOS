# Modos de NEXORA

- **Forge**: desarrollo, proyectos, herramientas y modelos locales.
- **Meteorology**: agente meteorolÃ³gico independiente; observaciones, modelos, alertas y sondeos mediante proveedores validados. En Beta 0.2: observaciÃ³n actual (simulada por defecto, Open-Meteo opt-in). Sin alertas ni sondeos todavÃ­a.
- **Security**: diagnÃ³stico defensivo y auditorÃ­as en sistemas autorizados.
- **Creator**: planificaciÃ³n y anÃ¡lisis de contenido digital.
- **Office**: documentos, estudio y productividad.

Cada modo puede tener dependencias, permisos, interfaz y memoria separados. El nÃºcleo comÃºn solo proporciona servicios transversales. Forge, Security, Creator y Office son hoy agentes base (stub) con memoria aislada.
