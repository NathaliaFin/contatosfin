"""Aplicativo instalavel (PWA): manifesto e service worker.

Os dois ficam na raiz do site, e nao em /static, por dois motivos: o service
worker so controla as paginas abaixo da pasta de onde e servido, e o nginx
guarda /static por 30 dias (uma troca de nome ou cor demoraria a chegar).

Nenhum dado de contato fica guardado no aparelho: o service worker so guarda
a pagina de "sem conexao".
"""

from flask import Blueprint, current_app, jsonify, send_from_directory, url_for

bp = Blueprint("pwa", __name__)


@bp.route("/manifest.webmanifest")
def manifesto():
    resposta = jsonify({
        "name": "Contatos Fin",
        "short_name": "Contatos",
        "description": "Os contatos institucionais da Fin em um só lugar.",
        "lang": "pt-BR",
        "start_url": url_for("contatos.lista"),
        "scope": "/",
        "display": "standalone",
        "orientation": "portrait",
        "background_color": "#0000A0",
        "theme_color": "#0000A0",
        "icons": [
            {"src": url_for("static", filename="img/app/icone-192.png"), "sizes": "192x192", "type": "image/png"},
            {"src": url_for("static", filename="img/app/icone-512.png"), "sizes": "512x512", "type": "image/png"},
            {"src": url_for("static", filename="img/app/icone-maskable-512.png"), "sizes": "512x512",
             "type": "image/png", "purpose": "maskable"},
        ],
    })
    resposta.mimetype = "application/manifest+json"
    resposta.headers["Cache-Control"] = "no-cache"
    return resposta


@bp.route("/sw.js")
def service_worker():
    resposta = send_from_directory(current_app.static_folder, "js/sw.js", mimetype="text/javascript", max_age=0)
    resposta.headers["Cache-Control"] = "no-cache"
    return resposta
