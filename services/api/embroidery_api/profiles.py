"""Private H0-04 profile catalog; identifiers mirror the frozen contract fixtures."""
import json
from pathlib import Path

from embroidery_contracts.profiles import ProfileCatalog

from .errors import ApiProblem


def load_profiles(path):
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
        return ProfileCatalog.model_validate(document)
    except (OSError, ValueError) as exc:
        raise ValueError(f"Profile catalog is invalid: {path}") from exc


def _entry(collection, identifier, label):
    entry = next((item for item in collection if item.profile_id == identifier), None)
    if entry is None:
        raise ApiProblem("INVALID_REQUEST", f"{label} desconocido: {identifier}.")
    return entry


def validate_settings(settings, catalog):
    machine = _entry(catalog.machines, settings.machine_profile, "machine_profile")
    if machine.profile_version != settings.machine_profile_version:
        raise ApiProblem("INVALID_REQUEST", "machine_profile_version no coincide con el perfil configurado.")
    hoop = _entry(catalog.hoops, settings.hoop_profile, "hoop_profile")
    if hoop.profile_id not in machine.hoop_profile_ids:
        raise ApiProblem("INVALID_REQUEST", "hoop_profile no pertenece a machine_profile.")
    if hoop.profile_version != settings.hoop.profile_version:
        raise ApiProblem("INVALID_REQUEST", "profile_version del bastidor no coincide con el perfil configurado.")
    for name in ("width_mm", "height_mm", "jef_hoop_code"):
        if getattr(hoop, name) != getattr(settings.hoop, name):
            raise ApiProblem("INVALID_REQUEST", f"El snapshot del bastidor no coincide en {name}.")
    fabric = _entry(catalog.fabrics, settings.fabric_profile, "fabric_profile")
    if fabric.profile_version != settings.fabric_profile_version:
        raise ApiProblem("INVALID_REQUEST", "fabric_profile_version no coincide con el perfil configurado.")
    _entry(catalog.thread_profiles, settings.thread_profile, "thread_profile")
    if settings.color_limit > machine.max_colors:
        raise ApiProblem("INVALID_REQUEST", "color_limit supera el máximo del perfil de máquina.")
    if settings.ai_provider != "none":
        provider = next((item for item in catalog.providers if item.provider_id == settings.ai_provider), None)
        if provider is None or not provider.available:
            raise ApiProblem("INVALID_REQUEST", f"ai_provider no disponible: {settings.ai_provider}.")
    return settings
