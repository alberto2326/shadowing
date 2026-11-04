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
   - *Setup script*: déjalo **vacío**. Las herramientas las instala `tools/setup.sh` al empezar cada tanda, con el
     mismo Python que se usa después (si se instalan también aquí, pueden acabar en otro Python y fallar).
5. **Primera tanda**: abre una sesión de Claude Code con el repo y escribe `/nueva-tanda`.
6. **Automatización**: en Claude Code, crea una tarea programada (sección de tareas programadas) con este repo y
   este entorno, que se ejecute el día 1 de cada mes por la mañana con este texto (si la tanda ya está hecha, termina sin hacer nada):
   > Ejecuta la skill /nueva-tanda de este repo de principio a fin y publica con `git push origin main`
   > (autorizo el push directo a main). Si la tanda del mes siguiente ya está hecha, no cambies nada.
   > Termina con un resumen de 3–4 líneas en español.

## Mantenimiento

- **Si una descarga de TED falla**: actualiza yt-dlp (`pip install -U yt-dlp`), fija la nueva versión en
  `tools/requirements.txt`.
- **Tamaño**: cada clip ocupa ~0,6 MB. La web solo conserva los clips de los últimos 60 días (`retain_days`).
- **Comprobar todo a mano**: `python3 tools/shadow.py check && python3 -m pytest -q tests`.

## Licencias

Audio de charlas TED (CC BY-NC-ND 4.0): uso no comercial, sin alterar, citando la charla con su enlace en cada
reproductor. Este repo no contiene audio de otras fuentes.
