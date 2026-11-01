# Shadowing de inglés de Alberto

Web para el móvil con **un clip nuevo cada día** de audio real (1–2 minutos) y un reproductor sincronizado
frase a frase. Alberto hace shadowing solo: **no hay feedback ni revisión**. El trabajo de Claude es fabricar
los clips por tandas (una vez al mes) y mantener el sistema.

Habla con Alberto en español (no es técnico: explica sin jerga). Los reproductores van en inglés.

## Reglas
- **Solo audio real** de charlas de **TED** (ted.com), con subtítulos humanos. Nunca TTS ni textos inventados.
- **Acento: solo americano general**, hablantes nativos de EE. UU., sin acento regional marcado (decisión de
  Alberto). Nada de británicos ni de no nativos.
- **Clips de 60–120 s** que empiecen y acaben en frase completa, con una sola voz.
- **Texto fiel al audio**: subtítulos contrastados con Whisper; si difieren, manda el audio (si las dos pasadas
  de Whisper no coinciden, se sigue a los subtítulos). Un clip solo se programa si pasa `verify`.
- **Variedad**: hombres y mujeres equilibrados, hablantes que no se repitan en días seguidos, temas alternos
  (negocio/marketing, trabajo, psicología y generales; Alberto trabaja en performance marketing).
- **Licencia TED** (CC BY-NC-ND): uso no comercial, citar siempre charla y enlace, no alterar el audio.
- Sin tokens ni credenciales en archivos. Nunca audio de terceros sin licencia que permita publicarlo.

## Cómo está organizado
- `config.json`: parámetros (zona horaria, duración, calidad del audio, días que se conservan, aviso).
- `data/calendario.json`: qué clip toca cada día. `data/clips/<slug>.json`: ficha de cada clip (fuente de todo).
- `site/`: lo que se publica. `index.html` elige sola el clip del día; `player.html?c=<slug>` es el único
  reproductor; `site/clips/` tiene `<slug>.mp3` y `<slug>.json`. Todo `site/` se genera con `tools/shadow.py`.
- `tools/shadow.py`: la herramienta (`--help`). `tests/`: pruebas. `work/`: descargas temporales (no se versiona).
- Nunca edites a mano `site/clips/` ni lo que hay entre `DATA:START` y `DATA:END` de `site/index.html`.

## Publicar
- Publicar = `git push origin main`. GitHub ejecuta `.github/workflows/publicar.yml`: si `shadow.py check` o las
  pruebas fallan, **no publica** y la web se queda como estaba. Antes de subir, ejecuta tú lo mismo:
  `python3 tools/shadow.py check && python3 -m pytest -q tests`.
- Alberto quiere que todo sea automático: nunca le pidas que fusione ramas a mano.

## Skills
- `/nueva-tanda`: fabrica los clips del mes siguiente, los programa (uno por día) y publica.
- `fabricar-clip`: el procedimiento de un clip (lo usa `/nueva-tanda`).

## Automatización
- Una tarea programada de Claude Code («Shadowing: tanda mensual», creada por Alberto desde la sección de tareas
  programadas con este repo y su entorno) arranca **cada lunes** una sesión nueva que ejecuta `/nueva-tanda`.
  Si ya hay clips hasta el final del mes siguiente, no hace nada; si no, fabrica la tanda y publica. Así, si un
  intento falla, el lunes siguiente lo vuelve a intentar. No depende de ninguna conversación.
- Nada se ejecuta a diario: el cambio de clip lo hace la propia página según la fecha. Si la tanda se acaba, la
  portada avisa y repasa clips anteriores; con menos de 7 días por delante, avisa de que quedan pocos.
