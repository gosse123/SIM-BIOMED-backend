"""Hôtes et origines de confiance dérivés de l'environnement.

Render peut suffixer le sous-domaine onrender.com d'un service en cas de
collision de nom (``simbiomed-api`` → ``simbiomed-api-abc123``). Le domaine
réel est injecté dans ``RENDER_EXTERNAL_HOSTNAME`` : impossible de le deviner
à l'avance dans le blueprint, on le lit donc à l'exécution.

L'origine du front suit la même logique via ``FRONTEND_ORIGIN`` : le proxy
nginx envoie ``Host: api`` alors que le navigateur vient du front, donc
Django compare l'``Origin`` à la liste CSRF de confiance et refuse avec un
403 si l'origine du front n'y figure pas.
"""

from __future__ import annotations


def _csv(raw: str | None) -> list[str]:
    """Découpe une liste séparée par des virgules, sans entrée vide."""
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _unique(values: list[str]) -> list[str]:
    """Conserve l'ordre en supprimant les doublons."""
    seen: list[str] = []
    for value in values:
        if value not in seen:
            seen.append(value)
    return seen


def allowed_hosts(configured: str | None, render_host: str | None) -> list[str]:
    """Hôtes acceptés : ceux déclarés, plus le domaine réel rendu par Render."""
    return _unique(_csv(configured) + _csv(render_host))


def cors_origins(configured: str | None, frontend_origin: str | None) -> list[str]:
    """Origines CORS : celles déclarées, plus celle de l'interface."""
    return _unique(_csv(configured) + _csv(frontend_origin))


def csrf_origins(
    configured: str | None,
    render_host: str | None,
    frontend_origin: str | None,
) -> list[str]:
    """Origines CSRF de confiance.

    Regroupe l'origine de l'API (repli hors Render), le domaine réel rendu par
    Render et l'origine du front, sans doublon.
    """
    own_origin = f"https://{render_host}" if render_host else ""
    return _unique(_csv(configured) + _csv(own_origin) + _csv(frontend_origin))
