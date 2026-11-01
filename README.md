# Shadowing de inglés

Web para el móvil: **https://alberto2326.github.io/shadowing/**

Cada día, un clip nuevo de 1–2 minutos de una charla TED (ponentes de EE. UU., americano general) con un
reproductor sincronizado frase a frase: velocidad 0.75x / 0.9x / 1x, pausa tras cada frase, repetir frase,
ocultar texto y sílabas tónicas subrayadas. La portada elige sola el clip del día; Claude Code fabrica los
clips por tandas, una vez al mes.

## Cómo funciona

| Pieza | Qué es |
|---|---|
| `site/` | La web que se publica: `index.html` (elige el clip del día), `player.html` (único reproductor) y `clips/` (audio y texto de cada clip) |
| `data/` | La fuente: `calendario.json` (qué clip toca cada día) y `clips/<slug>.json` (ficha de cada clip) |
| `tools/shadow.py` | La herramienta: descarga de TED, Whisper, alineado, recorte, verificación, calendario y comprobación (`--help`) |
| `tests/` | Pruebas automáticas |
| `.github/workflows/publicar.yml` | Publica `site/` en GitHub Pages solo si pasan la comprobación y las pruebas |
| `.claude/skills/` | Procedimientos para Claude: `nueva-tanda` y `fabricar-clip` |
| `config.json` | Parámetros: zona horaria, duración de los clips, calidad del audio, días que se conservan |

## Cómo montarlo desde cero

Pensado para replicarlo en otra cuenta. Solo hace falta una cuenta de GitHub y Claude Code en la web.

1. **Repo**: crea un repo público en GitHub (por ejemplo `shadowing`) y sube este contenido. Si quieres, cambia
   `timezone` en `config.json`. La web quedará en `https://<usuario>.github.io/<repo>/`.
2. **GitHub Pages**: en el repo, *Settings → Pages → Build and deployment → Source: GitHub Actions*.
   Cada `push` a `main` publica la web si todo está bien.
3. **Claude con acceso a GitHub**: conecta GitHub en https://claude.ai/connect-github e instala la app de
   Claude en el repo.
4. **Entorno de Claude Code** (menú del entorno en la barra de título de la sesión → *Edit*):
   - *Network access* → *Custom* → *Allowed domains* (deja marcada la lista de gestores de paquetes):
     ```
     ted.com
     *.ted.com
     *.tedcdn.com
     huggingface.co
     *.huggingface.co
     *.hf.co
     ```
   - *Setup script* (instala las herramientas y descarga el modelo de Whisper al crear cada sesión):
     ```bash
     python3 -m pip install -q --root-user-action=ignore "yt-dlp==2026.10.26" "faster-whisper==1.2.1" "numpy==2.5.3" "pytest==9.2.0"
     python3 -c "from faster_whisper import WhisperModel; WhisperModel('small.en', device='cpu', compute_type='int8')" >/dev/null
     ```
5. **Primera tanda**: abre una sesión de Claude Code con el repo y escribe `/nueva-tanda`.
6. **Automatización**: crea una sesión de Claude Code con el repo (por ejemplo «Shadowing: tanda mensual (no
   borrar)»), escríbele que autorizas el push directo a `main`, y pide a Claude que cree en esa sesión dos tareas
   programadas mensuales (días 15 y 25) que ejecuten `/nueva-tanda`.

## Mantenimiento

- **Si una descarga de TED falla**: actualiza yt-dlp (`pip install -U yt-dlp`), fija la nueva versión en
  `tools/requirements.txt`, `tools/setup.sh` y el *Setup script* del entorno.
- **Tamaño**: cada clip ocupa ~0,6 MB. La web solo conserva los clips de los últimos 60 días (`retain_days`).
- **Comprobar todo a mano**: `python3 tools/shadow.py check && python3 -m pytest -q tests`.

## Licencias

Audio de charlas TED (CC BY-NC-ND 4.0): uso no comercial, sin alterar, citando la charla con su enlace en cada
reproductor. Este repo no contiene audio de otras fuentes.
