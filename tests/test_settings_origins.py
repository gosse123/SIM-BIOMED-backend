"""Origines et hôtes de confiance de config.settings.production.

Trois cas de figure sont couverts :
  - le domaine onrender.com rendu par Render est suffixé en cas de collision ;
  - l'origine du front doit être acceptée par le CSRF sinon le proxy nginx
    (Host = api) provoque un 403 sur toute requête POST du navigateur ;
  - la liste déclarée dans le blueprint reste la source de repli hors Render.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from config.settings.origins import allowed_hosts, cors_origins, csrf_origins

REPO_ROOT = Path(__file__).resolve().parents[1]

PROBE = """
import json

import django

django.setup()

from django.conf import settings

print(
    json.dumps(
        {
            "allowed_hosts": list(settings.ALLOWED_HOSTS),
            "cors": list(settings.CORS_ALLOWED_ORIGINS),
            "csrf": list(settings.CSRF_TRUSTED_ORIGINS),
        }
    )
)
"""


def _load_production_settings(**env):
    """Charge config.settings.production dans un interpréteur vierge."""
    process_env = os.environ.copy()
    process_env.update(
        {
            "DJANGO_SETTINGS_MODULE": "config.settings.production",
            "DJANGO_SECRET_KEY": "cle-de-test",
        }
    )
    process_env.update(env)
    result = subprocess.run(
        [sys.executable, "-c", PROBE],
        cwd=REPO_ROOT,
        env=process_env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_allowed_hosts_repli_hors_render():
    assert allowed_hosts("api.example.com", "") == ["api.example.com"]


def test_allowed_hosts_ajoute_le_domaine_reel_de_render():
    assert allowed_hosts("api.example.com", "api-abc123.example.com") == [
        "api.example.com",
        "api-abc123.example.com",
    ]


def test_allowed_hosts_ne_duplique_pas():
    assert allowed_hosts("api-abc123.example.com", "api-abc123.example.com") == [
        "api-abc123.example.com"
    ]


def test_allowed_hosts_ignore_les_vides_et_les_espaces():
    assert allowed_hosts(" a.example.com , , b.example.com ", None) == [
        "a.example.com",
        "b.example.com",
    ]


def test_cors_ajoute_l_origine_du_front():
    assert cors_origins("", "https://front.example.com") == ["https://front.example.com"]


def test_cors_ne_duplique_pas_l_origine_du_front():
    assert cors_origins("https://front.example.com", "https://front.example.com") == [
        "https://front.example.com"
    ]


def test_csrf_fait_confiance_a_l_origine_du_front():
    """Sans cette origine, Host=api + Origin=front donne un 403 CSRF."""
    origins = csrf_origins("https://api.example.com", "", "https://front.example.com")
    assert "https://front.example.com" in origins
    assert "https://api.example.com" in origins


def test_csrf_derive_l_origine_propre_depuis_render():
    assert csrf_origins("", "api.example.com", "") == ["https://api.example.com"]


def test_csrf_ne_duplique_pas_l_origine_propre():
    assert csrf_origins("https://api-abc.example.com", "api-abc.example.com", "") == [
        "https://api-abc.example.com"
    ]


def test_csrf_conserve_l_ordre_sans_doublon():
    assert csrf_origins(
        "https://api.example.com, https://api.example.com",
        "api.example.com",
        "https://front.example.com",
    ) == ["https://api.example.com", "https://front.example.com"]


def test_production_utilise_le_domaine_suffixe_de_render():
    settings = _load_production_settings(
        ALLOWED_HOSTS="simbiomed-api.onrender.com",
        CORS_ALLOWED_ORIGINS="",
        CSRF_TRUSTED_ORIGINS="https://simbiomed-api.onrender.com",
        FRONTEND_ORIGIN="https://simbiomed-frontend-abc123.onrender.com",
        RENDER_EXTERNAL_HOSTNAME="simbiomed-api-abc123.onrender.com",
    )
    assert settings["allowed_hosts"] == [
        "simbiomed-api.onrender.com",
        "simbiomed-api-abc123.onrender.com",
    ]
    assert settings["cors"] == ["https://simbiomed-frontend-abc123.onrender.com"]
    assert settings["csrf"] == [
        "https://simbiomed-api.onrender.com",
        "https://simbiomed-api-abc123.onrender.com",
        "https://simbiomed-frontend-abc123.onrender.com",
    ]


def test_production_sans_render_garde_les_origines_du_blueprint():
    settings = _load_production_settings(
        ALLOWED_HOSTS="api.local",
        CORS_ALLOWED_ORIGINS="https://front.local",
        CSRF_TRUSTED_ORIGINS="https://api.local",
        FRONTEND_ORIGIN="",
        RENDER_EXTERNAL_HOSTNAME="",
    )
    assert settings["allowed_hosts"] == ["api.local"]
    assert settings["cors"] == ["https://front.local"]
    assert settings["csrf"] == ["https://api.local"]
