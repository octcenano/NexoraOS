"""Perfiles de juego de NGNE: seis perfiles, adaptados al enlace y al hardware.

Los perfiles declaran intenciones (cola preferida, DNS, gestión de tráfico).
Nada se aplica aquí: el optimizador verifica compatibilidad, captura el
estado previo y exige consentimiento para lo privilegiado.

Adaptación (Nexora Adapt):
  - hardware compacto: CAKE se sustituye por fq-codel (menor coste de CPU).
  - qdiscs del kernel disponibles: si la cola preferida no existe, se usa la
    alternativa o se declara que no hay cola segura que tocar.
  - enlace real Wi-Fi con perfil Ethernet: aviso de revisar señal primero.
  - custom: parámetros del usuario, validados contra una lista cerrada.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

APPLICABLE_QDISCS = ("fq_codel", "cake")

GAMING_PROFILES: Dict[str, Dict[str, Any]] = {
    "balanced": {
        "label": "Balanced",
        "description": "Equilibrio entre la partida y el resto del tráfico",
        "qdisc": "fq_codel",
        "qdisc_params": {},
        "dns": "keep",
        "traffic": "fair",
        "notes": "fq-codel controla el bufferbloat de forma justa para todo el "
                 "tráfico; sin priorizar UDP indiscriminado",
    },
    "low_latency": {
        "label": "Low Latency",
        "description": "Respuesta del enlace por delante de la descarga",
        "qdisc": "cake",
        "qdisc_params": {"diffserv": "diffserv4"},
        "dns": "keep",
        "traffic": "prioritize_game",
        "notes": "CAKE con diffserv4; la priorización por puertos del juego se "
                 "propone y exige aprobación explícita",
    },
    "wifi": {
        "label": "Wi-Fi",
        "description": "Ajustado a enlaces inalámbricos con pérdida variable",
        "qdisc": "fq_codel",
        "qdisc_params": {},
        "dns": "keep",
        "traffic": "fair",
        "notes": "en Wi-Fi la causa dominante suele ser el propio enlace: el "
                 "diagnóstico de señal y banda manda sobre los ajustes",
    },
    "ethernet": {
        "label": "Ethernet",
        "description": "Enlace cableado: cola activa y poco más",
        "qdisc": "cake",
        "qdisc_params": {},
        "dns": "keep",
        "traffic": "fair",
        "notes": "con duplex completo y sin errores, la cola es la palanca principal",
    },
    "limited_hardware": {
        "label": "Limited Hardware",
        "description": "Equipos modestos: minimizar el coste de CPU de la cola",
        "qdisc": "fq_codel",
        "qdisc_params": {},
        "dns": "keep",
        "traffic": "fair",
        "notes": "fq-codel cuesta menos CPU que CAKE; se evita CAKE en hardware limitado",
    },
    "custom": {
        "label": "Custom",
        "description": "Parámetros definidos por el usuario, validados",
        "qdisc": None,
        "qdisc_params": {},
        "dns": "keep",
        "traffic": "none",
        "notes": "sin valores por defecto: el usuario declara cada parámetro y se valida",
    },
}

PROFILE_ORDER = ("balanced", "low_latency", "wifi", "ethernet",
                 "limited_hardware", "custom")

CUSTOM_ALLOWED_KEYS = ("qdisc", "qdisc_params", "dns", "traffic", "notes")


def adapt_profile(name: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Devuelve el perfil efectivo adaptado al contexto real del equipo.

    context (todo opcional):
      - hardware_tier: "compact" | "balanced" | "expanded"
      - link_type: "wifi" | "ethernet" | "unknown"
      - qdiscs_available: lista de colas que el kernel soporta
      - custom_params: solo para el perfil custom
    Nunca aplica nada: solo declara qué se aplicaría.
    """
    if name not in GAMING_PROFILES:
        raise ValueError(f"Perfil desconocido: {name}. Opciones: {list(PROFILE_ORDER)}")
    context = dict(context or {})
    base = GAMING_PROFILES[name]
    effective: Dict[str, Any] = {}
    for key, value in base.items():
        effective[key] = dict(value) if isinstance(value, dict) else value
    adaptations: List[str] = []

    if name == "custom":
        for key, value in context.get("custom_params", {}).items():
            if key not in CUSTOM_ALLOWED_KEYS:
                raise ValueError(f"Parámetro custom desconocido: {key}. "
                                 f"Permitidos: {list(CUSTOM_ALLOWED_KEYS)}")
            effective[key] = value
            adaptations.append(f"custom: {key} definido por el usuario")
        qdisc = effective.get("qdisc")
        if qdisc is not None and qdisc not in APPLICABLE_QDISCS:
            raise ValueError(f"qdisc custom no soportado: {qdisc}. "
                             f"Opciones: {list(APPLICABLE_QDISCS)} o None")
    else:
        tier = context.get("hardware_tier")
        if tier == "compact" and effective["qdisc"] == "cake":
            effective["qdisc"] = "fq_codel"
            effective["qdisc_params"] = {}
            adaptations.append("hardware compacto: CAKE sustituido por fq-codel "
                               "(menor coste de CPU)")

    available = context.get("qdiscs_available")
    if available is not None and effective["qdisc"] is not None:
        if effective["qdisc"] not in available:
            fallback = "cake" if effective["qdisc"] == "fq_codel" else "fq_codel"
            if fallback in available:
                adaptations.append(f"{effective['qdisc']} no disponible en este kernel: "
                                   f"se usa {fallback}")
                effective["qdisc"] = fallback
            else:
                adaptations.append(f"{effective['qdisc']} no disponible en este kernel y "
                                   "sin alternativa soportada: no se toca nada")
                effective["qdisc"] = None

    link = context.get("link_type")
    if link == "wifi" and name == "ethernet":
        adaptations.append("el enlace real es Wi-Fi: revisa el diagnóstico de señal "
                           "y banda antes de aplicar ajustes pensados para Ethernet")

    return {"name": name, "label": base["label"],
            "effective": effective, "adaptations": adaptations}
