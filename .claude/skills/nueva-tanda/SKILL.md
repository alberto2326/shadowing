---
name: nueva-tanda
description: Fabrica la tanda de clips de shadowing del mes siguiente (uno por día), la programa y publica la web. Úsala en la tarea mensual (días 15 y 25), cuando `shadow.py status` avise de que quedan pocos días o cuando lo pida Alberto.
---

# Nueva tanda de clips

1. Ponte al día con GitHub (en esta sesión nunca hay trabajo local que conservar):
   `git fetch origin main && git checkout main && git reset --hard origin/main`
2. `bash tools/setup.sh`. Si falta acceso a ted.com o huggingface.co, **para** y explica qué dominio falta
   (Network access del entorno). No inventes clips ni transcripciones.
3. `python3 tools/shadow.py status`. Objetivo: que haya clip para cada día **hasta el último día del mes
   siguiente**. Si ya lo hay (por ejemplo, porque la tarea del día 15 ya lo hizo), termina aquí sin cambiar nada.
4. Haz la lista de charlas antes de fabricar: solo americano general, mitad hombres y mitad mujeres, temas
   alternos. De una charla puedes sacar 2 clips distintos, pero no en días seguidos. Evita charlas ya usadas en
   los últimos meses (mira `data/clips/`).
5. Para cada clip, sigue la skill `fabricar-clip`. Si uno no pasa `verify`, descártalo y elige otro tramo.
6. `python3 tools/shadow.py site` (vuelca el calendario y retira los clips de hace más de `retain_days`).
7. `python3 tools/shadow.py check && python3 -m pytest -q tests`. Tiene que salir todo bien.
8. `git add -A && git commit -m "Shadowing: tanda hasta AAAA-MM-DD"` y `git push origin main` (Alberto autorizó
   el push directo a `main` en la tarea programada). Después, borra `work/`.
9. Resume en 3–4 líneas: cuántos clips nuevos, hasta qué fecha hay clips y cualquier problema.
