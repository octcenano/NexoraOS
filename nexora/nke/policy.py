"""NKE Policy Engine: convierte hallazgos y peticiones de perfiles en acciones.

Cada acción pertenece a una categoría:
  A (automática): reversible, de bajo riesgo, aplicable sin preguntar.
  B (supervisada): se prepara y valida, pero exige aprobación del usuario.
  C (protegida): nunca se ejecuta desde NKE; solo se documenta/propone.

Los conflictos entre perfiles se resuelven con prioridades explícitas: el
modo primario gana y existen límites globales (RAM reservable <= 80%).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

CATEGORY_A = "automatic"
CATEGORY_B = "supervised"
CATEGORY_C = "protected"

# Acciones conocidas: kind -> (categoría, reversible, descripción)
ACTION_CATALOG: Dict[str, Dict[str, Any]] = {
    "renice_agent": {"category": CATEGORY_A, "reversible": True,
                     "description": "Bajar prioridad (nice) de procesos de agentes secundarios"},
    "cgroup_limit": {"category": CATEGORY_A, "reversible": True,
                     "description": "Fijar cpu.max/memory.max del slice de nexora (cgroups v2)"},
    "reduce_agent_ram": {"category": CATEGORY_A, "reversible": True,
                         "description": "Reducir el límite de RAM de los agentes en el slice"},
    "pause_secondary_agents": {"category": CATEGORY_B, "reversible": True,
                               "description": "Congelar (SIGSTOP) procesos de agentes secundarios"},
    "deprioritize_secondary": {"category": CATEGORY_A, "reversible": True,
                               "description": "Renice de procesos secundarios bajo presión de CPU"},
    "throttle_secondary_io": {"category": CATEGORY_B, "reversible": True,
                              "description": "Límites de E/S (io.max) para el slice de nexora"},
    "set_governor": {"category": CATEGORY_B, "reversible": True,
                     "description": "Cambiar el gobernador de cpufreq (afecta a todo el sistema)"},
    "set_swappiness": {"category": CATEGORY_B, "reversible": True,
                       "description": "Cambiar vm.swappiness (afecta a todo el sistema)"},
    "change_dns": {"category": CATEGORY_B, "reversible": True,
                   "description": "Cambiar la configuración DNS del sistema"},
    "load_kernel_module": {"category": CATEGORY_C, "reversible": False,
                           "description": "Cargar un módulo del kernel (modprobe): operación privilegiada"},
    "kernel_cmdline": {"category": CATEGORY_C, "reversible": False,
                       "description": "Cambiar parámetros de arranque"},
}


@dataclass(frozen=True)
class Action:
    kind: str
    category: str
    reversible: bool
    target: str
    params: Dict[str, Any]
    justification: str
    rollback: Dict[str, Any] = field(default_factory=dict)


class PolicyEngine:
    """Decide qué acciones pueden aplicarse según capacidades y estado."""

    def __init__(self, capabilities: Dict[str, Any]):
        self.caps = capabilities

    def decide(self, findings: List[Dict[str, Any]], profile_requests: Optional[List[Dict[str, Any]]] = None,
               primary_mode: Optional[str] = None) -> Dict[str, List[Action]]:
        """Devuelve {categoría: [acciones]} ordenadas por prioridad.

        - Categoría A: aplicables automáticamente.
        - Categoría B: requieren aprobación (se devuelven listas para el usuario).
        - Categoría C: nunca se ejecutan; se devuelven como propuesta documentada.
        """
        result: Dict[str, List[Action]] = {CATEGORY_A: [], CATEGORY_B: [], CATEGORY_C: []}
        for f in findings:
            for kind in f.get("suggests", []):
                action = self._action_for(kind, f, primary_mode)
                if action is not None:
                    result[action.category].append(action)

        for req in profile_requests or []:
            action = self._action_for(req.get("kind", ""), req, primary_mode, from_profile=True)
            if action is not None:
                result[action.category].append(action)

        # Deduplicación por (kind, target) conservando orden de prioridad.
        for cat in result:
            seen, uniq = set(), []
            for a in result[cat]:
                key = (a.kind, a.target)
                if key not in seen:
                    seen.add(key)
                    uniq.append(a)
            result[cat] = uniq
        return result

    def _action_for(self, kind: str, source: Dict[str, Any], primary_mode: Optional[str],
                    from_profile: bool = False) -> Optional[Action]:
        spec = ACTION_CATALOG.get(kind)
        if spec is None:
            return None
        cat = spec["category"]
        target = self._target_for(kind, source)
        params = dict(source.get("params", {}))
        why = source.get("detail", "petición de perfil") if not from_profile else \
            f"perfil '{source.get('mode', '?')}' solicita '{kind}'"
        action = Action(kind=kind, category=cat, reversible=spec["reversible"],
                        target=target, params=params, justification=why)

        # Restricciones por capacidad real: si la interfaz no existe, no se propone.
        if kind in ("cgroup_limit", "reduce_agent_ram", "throttle_secondary_io") and not self.caps.get("can_cgroup_limits"):
            return None
        if kind == "set_governor" and not self.caps.get("can_cpufreq_tuning"):
            return None
        if kind in ("renice_agent", "deprioritize_secondary") and not (source.get("top_processes") or source.get("suggests")):
            if kind == "renice_agent":
                return None
        return action

    @staticmethod
    def _target_for(kind: str, source: Dict[str, Any]) -> str:
        if kind in ("renice_agent", "deprioritize_secondary"):
            top = (source.get("top_processes") or [{}])[0]
            return str(top.get("pid", "agentes-nexora"))
        if kind in ("cgroup_limit", "reduce_agent_ram", "throttle_secondary_io"):
            return "nexora.slice"
        if kind == "set_governor":
            return "cpu0"
        if kind == "set_swappiness":
            return "vm.swappiness"
        return source.get("target", "sistema")
