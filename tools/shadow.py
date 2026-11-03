#!/usr/bin/env python3
"""Herramienta del sistema de shadowing: fabrica clips, los programa (uno por día) y genera la web.

Lo mecánico lo hace este script; lo que requiere criterio (elegir el pasaje, marcar sílabas tónicas,
escribir los puntos de escucha) lo hace Claude siguiendo la skill `fabricar-clip`.

Fabricar un clip:
  download <url-ted>              audio de la charla (work/<id>.wav, 16 kHz mono) + subtítulos humanos
  srt <id> [desde] [hasta]        subtítulos con tiempos, para elegir el tramo
  words <id> <ini> <fin>          palabras con tiempos según Whisper (work/<id>.words.json)
  align <slug>                    tiempos de cada línea del descriptor data/clips/<slug>.json
  build <slug>                    recorta el mp3 y genera site/clips/<slug>.json
  verify <slug> [--force]         vuelve a transcribir el mp3 y lo compara con el texto
  add <slug> [--fecha F]          lo programa en el calendario (por defecto, el primer día libre)

Web y calendario:
  render [slug]                   regenera site/clips/<slug>.json (o todos) sin tocar el audio
  site                            vuelca el calendario en site/index.html y retira clips antiguos
  status                          clip de hoy y hasta qué día hay clips
  check                           comprobación completa; falla si algo no cuadra (la usa GitHub antes de publicar)

Rutas: data/ (fuente: calendario y descriptores), site/ (lo que se publica), work/ (temporal, no se versiona).
La configuración está en config.json.
"""
import argparse, datetime as dt, difflib, glob, json, os, re, subprocess, sys

ROOT = os.environ.get("SHADOW_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "config.json")
DATA = os.path.join(ROOT, "data")
DESC = os.path.join(DATA, "clips")
CAL = os.path.join(DATA, "calendario.json")
SITE = os.path.join(ROOT, "site")
SITE_CLIPS = os.path.join(SITE, "clips")
INDEX = os.path.join(SITE, "index.html")
WORK = os.path.join(ROOT, "work")
PAD0, PAD1 = 0.4, 0.3  # margen del recorte antes y después del tramo (s)


# ---------------------------------------------------------------- utilidades
def jload(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def jsave(p, obj):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")


def cfg():
    return jload(CONFIG)


def today():
    from zoneinfo import ZoneInfo
    return dt.datetime.now(ZoneInfo(cfg()["timezone"])).date()


def norm(w):
    return re.sub(r"[^a-z0-9]", "", w.lower())


def plain_tokens(line):
    """Palabras de una línea sin marcas: quita <b>, «/» y separa «30,000» como lo escribe Whisper («30 000»)."""
    txt = re.sub(r"<[^>]+>", "", line).replace("/", " ")
    txt = re.sub(r"(\d),(\d)", r"\1 \2", txt)
    return [t for t in re.split(r"[\s\u2014-]+", txt) if norm(t)]


# Terminaciones que en inglés nunca llevan el acento: si aparecen marcadas como tónicas, el marcado está mal
# (p. ej. «ask<b>ing</b>» en vez de «<b>ask</b>ing», «ques<b>tion</b>» en vez de «<b>ques</b>tion»).
BAD_STRESS = re.compile(r"[A-Za-z]<b>(ing|ed|es|ly|s|er|ers|ness|ment|tion|sion)</b>(?![A-Za-z])")


def stress_problems(lines):
    """Marcas de sílaba tónica puestas en una terminación átona."""
    return [m.group(0) for l in lines for m in BAD_STRESS.finditer(l)]


# Vocabulario avanzado: pocas palabras por clip (nivel C1 o superior), cada una con su explicación.
# Ficha: "vocab": [{"w": "palabra tal como suena en el texto", "en": "definition", "es": "traducción"}]
VOCAB_MAX = 4


def vocab_problems(d):
    """Problemas del vocabulario de una ficha (lista vacía si está bien o si no tiene)."""
    v = d.get("vocab", [])
    errs = []
    if len(v) > VOCAB_MAX:
        errs.append(f"vocabulario: {len(v)} palabras (máximo {VOCAB_MAX}: solo las realmente difíciles)")
    text = " ".join(re.sub(r"<[^>]+>", "", l) for l in d.get("lines", []))
    vistas = set()
    for e in v:
        w = (e.get("w") or "").strip()
        if not w or not (e.get("en") or "").strip() or not (e.get("es") or "").strip():
            errs.append(f"vocabulario: cada palabra necesita w, en y es ({e})")
            continue
        if w.lower() in vistas:
            errs.append(f"vocabulario: «{w}» repetida")
        vistas.add(w.lower())
        if not re.search(r"(?<![\w'-])" + re.escape(w) + r"(?![\w])", text, re.I):
            errs.append(f"vocabulario: «{w}» no aparece tal cual en el texto del clip")
    return errs


def mmss(x):
    return f"{int(x) // 60:02d}:{int(x) % 60:02d}"


def desc_path(slug):
    return os.path.join(DESC, slug + ".json")


def ted_id(url):
    m = re.search(r"ted\.com/talks/([\w-]+)", url)
    if not m:
        sys.exit("Solo se admiten charlas de ted.com (https://www.ted.com/talks/...).")
    return "ted-" + m.group(1)[:60]


# ---------------------------------------------------------------- fabricar un clip
def cmd_download(a):
    os.makedirs(WORK, exist_ok=True)
    vid = ted_id(a.url)
    for f in glob.glob(os.path.join(WORK, vid + ".*")):
        os.remove(f)
    subprocess.run([sys.executable, "-m", "yt_dlp", "-q", "--no-warnings", "-f", "bestaudio/best",
                    "-o", os.path.join(WORK, f"{vid}.%(ext)s"),
                    "--write-subs", "--sub-langs", "en,en-US", "--convert-subs", "srt", a.url], check=True)
    src = [f for f in glob.glob(os.path.join(WORK, vid + ".*")) if not f.endswith((".srt", ".vtt"))]
    if not src or os.path.getsize(src[0]) == 0:
        sys.exit("Descarga vacía.")
    wav = os.path.join(WORK, vid + ".wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src[0], "-vn", "-ac", "1", "-ar", "16000", wav], check=True)
    os.remove(src[0])
    subs = glob.glob(os.path.join(WORK, vid + "*.srt"))
    print(f"id: {vid}")
    print("Subtítulos humanos:", subs[0] if subs else "NINGUNO (elige otra charla)")


def _srt_time(t):
    h, m, s = t.replace(",", ".").split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def srt_entries(path):
    """(inicio, fin, texto) de un .srt. Corrige el formato de TED, que mete «hh:mm:ss.mmm -- hh:mm:ss.mmm» en el texto."""
    out = []
    emb = re.compile(r"(\d\d:\d\d:\d\d[.,]\d{3}) -- (\d\d:\d\d:\d\d[.,]\d{3})")
    for blk in open(path, encoding="utf-8").read().strip().split("\n\n"):
        ln = blk.strip().split("\n")
        if len(ln) < 2 or "-->" not in ln[1]:
            continue
        s, e = [_srt_time(x.strip()) for x in ln[1].split("-->")]
        parts = emb.split(" ".join(ln[2:]))
        if parts[0].strip():
            out.append((s, e, parts[0].strip()))
        for i in range(1, len(parts) - 2, 3):
            if parts[i + 2].strip():
                out.append((_srt_time(parts[i]), _srt_time(parts[i + 1]), parts[i + 2].strip()))
    out.sort()
    return [x for i, x in enumerate(out) if i == 0 or x[2] != out[i - 1][2]]


def cmd_srt(a):
    subs = sorted(glob.glob(os.path.join(WORK, a.id + "*.srt")))
    if not subs:
        sys.exit("No hay subtítulos para " + a.id)
    for s, e, t in srt_entries(subs[0]):
        if (a.desde is None or e >= a.desde) and (a.hasta is None or s <= a.hasta):
            print(f"{s:8.2f} {e:8.2f}  {t}")


def _whisper():
    from faster_whisper import WhisperModel
    name = cfg()["whisper_model"]
    try:
        return WhisperModel(name, device="cpu", compute_type="int8", local_files_only=True)
    except Exception:
        return WhisperModel(name, device="cpu", compute_type="int8")


def _pcm(path, ss=None, to=None):
    import numpy as np
    cmd = ["ffmpeg", "-loglevel", "error"] + (["-ss", str(ss), "-to", str(to)] if ss is not None else [])
    cmd += ["-i", path, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768


def _transcribe(audio):
    segs, _ = _whisper().transcribe(audio, language="en", beam_size=5, word_timestamps=True,
                                    condition_on_previous_text=False)
    return [(w.start, w.end, w.word.strip()) for s in segs for w in s.words]


def cmd_words(a):
    s0 = max(0.0, a.ini - 3)
    words = [(round(s + s0, 2), round(e + s0, 2), t)
             for s, e, t in _transcribe(_pcm(os.path.join(WORK, a.id + ".wav"), s0, a.fin + 3))]
    jsave(os.path.join(WORK, a.id + ".words.json"), words)
    print(" ".join(w[2] for w in words if a.ini - 0.5 <= w[0] <= a.fin + 0.5))


def align(d, words):
    """Calcula las cues {s, e, t} de d["lines"] con las palabras de Whisper. Devuelve (cues, start, end, líneas_sin_pareja)."""
    lines = d["lines"]
    ws = [w for w in words if d["start"] - 0.6 <= w[0] <= d["end"] + 0.4]
    seqA = [(i, norm(t)) for i, l in enumerate(lines) for t in plain_tokens(l)]
    sm = difflib.SequenceMatcher(None, [x[1] for x in seqA], [norm(w[2]) for w in ws], autojunk=False)
    first, last = {}, {}
    for i, j, n in sm.get_matching_blocks():
        for k in range(n):
            li, w = seqA[i + k][0], ws[j + k]
            first[li] = min(first.get(li, w[0]), w[0])
            last[li] = max(last.get(li, 0), w[1])
    missing = [i for i in range(len(lines)) if i not in first]
    for i in missing:  # líneas sin coincidencia: se interpolan entre sus vecinas
        prev = max([last[j] for j in range(i) if j in last], default=d["start"])
        nxt = min([first[j] for j in range(i + 1, len(lines)) if j in first], default=d["end"])
        first[i] = last[i] = (prev + nxt) / 2
    cues = []
    for i, l in enumerate(lines):
        s = first[i] - 0.12 if i == 0 else max(d["start"] - 0.3, first[i] - 0.12)
        cues.append({"s": round(s, 2), "t": l})
    for i, q in enumerate(cues):
        q["e"] = cues[i + 1]["s"] if i + 1 < len(cues) else round(max(last[i] + 0.15, q["s"] + 0.5), 2)
    return cues, round(cues[0]["s"] + 0.3, 2), round(cues[-1]["e"] - 0.1, 2), missing


def cmd_align(a):
    p = desc_path(a.slug)
    d = jload(p)
    d["cues"], d["start"], d["end"], missing = align(d, jload(os.path.join(WORK, d["video_id"] + ".words.json")))
    d.pop("verified", None)
    jsave(p, d)
    c = cfg()
    dur = d["end"] - d["start"]
    print(f"{a.slug}: {dur:.1f} s · líneas sin coincidencia: {missing}")
    if not c["clip_min_s"] <= dur <= c["clip_max_s"]:
        print(f"AVISO: fuera de {c['clip_min_s']}–{c['clip_max_s']} s")


def clip_data(d):
    """Datos públicos del clip (site/clips/<slug>.json): tiempos relativos al mp3 recortado."""
    off = max(0, d["start"] - PAD0)
    return {"title": d["title"], "source": d["source"], "url": d["url"],
            "segment": f'{mmss(d["start"])}–{mmss(d["end"])} ({round(d["end"] - d["start"])} s)',
            "listen_for": d.get("listen_for", ""),
            "vocab": d.get("vocab", []),
            "cues": [{"s": round(x["s"] - off, 2), "e": round(x["e"] - off, 2), "t": x["t"]} for x in d["cues"]]}


def cmd_render(a):
    slugs = [a.slug] if a.slug else [x["slug"] for x in jload(CAL)["clips"]
                                     if os.path.exists(os.path.join(SITE_CLIPS, x["slug"] + ".mp3"))]
    for s in slugs:
        jsave(os.path.join(SITE_CLIPS, s + ".json"), clip_data(jload(desc_path(s))))
    print(f"{len(slugs)} clip(s) regenerados")


def cmd_build(a):
    d = jload(desc_path(a.slug))
    os.makedirs(SITE_CLIPS, exist_ok=True)
    s0, s1 = max(0, d["start"] - PAD0), d["end"] + PAD1
    mp3 = os.path.join(SITE_CLIPS, d["slug"] + ".mp3")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(s0), "-to", str(s1),
                    "-i", os.path.join(WORK, d["video_id"] + ".wav"),
                    "-codec:a", "libmp3lame", "-b:a", f'{cfg()["mp3_kbps"]}k', "-ac", "1", mp3], check=True)
    jsave(os.path.join(SITE_CLIPS, d["slug"] + ".json"), clip_data(d))
    print(mp3)


def compare(cue_lines, words, offset):
    """Compara el texto con lo que oye Whisper en el mp3. Devuelve (no_oídas, sobrantes, fuera_de_línea)."""
    A, L = [], []
    for i, c in enumerate(cue_lines):
        for t in plain_tokens(c["t"]):
            A.append(norm(t)); L.append(i)
    B = [norm(w[2]) for w in words]
    blocks = difflib.SequenceMatcher(None, A, B, autojunk=False).get_matching_blocks()
    mA = {i + k for i, j, n in blocks for k in range(n)}
    mB = {j + k for i, j, n in blocks for k in range(n)}
    bad = [(A[i + k], round(words[j + k][0], 2)) for i, j, n in blocks for k in range(n)
           if not cue_lines[L[i + k]]["s"] - offset - 0.35 <= words[j + k][0] <= cue_lines[L[i + k]]["e"] - offset + 0.2]
    return ([A[i] for i in range(len(A)) if i not in mA], [B[i] for i in range(len(B)) if i not in mB and B[i]], bad)


def cmd_verify(a):
    p = desc_path(a.slug)
    d = jload(p)
    audio = _pcm(os.path.join(SITE_CLIPS, d["slug"] + ".mp3"))
    words = _transcribe(audio)
    missing, extra, bad = compare(d["cues"], words, max(0, d["start"] - PAD0))
    n = sum(len(plain_tokens(c["t"])) for c in d["cues"])
    print(f"{d['slug']}: {len(audio) / 16000:.1f} s")
    print("  palabras del texto no oídas:", missing)
    print("  palabras oídas que no están en el texto:", extra)
    print("  palabras fuera de su línea:", bad[:10], len(bad))
    ok = len(missing) <= max(2, n // 50) and len(bad) <= max(2, n // 25)
    if ok or a.force:
        d["verified"] = today().isoformat() + ("" if ok else " (forzado: diferencias revisadas, ver notas)")
        jsave(p, d)
        print("OK: verificado")
    else:
        sys.exit("NO VERIFICADO: corrige el texto o el tramo. Usa --force solo si son errores del reconocedor ya revisados (y explícalo en notas).")


# ---------------------------------------------------------------- calendario y web
def cmd_add(a):
    d = jload(desc_path(a.slug))
    cal = jload(CAL)
    if any(x["slug"] == a.slug for x in cal["clips"]):
        sys.exit(f"{a.slug} ya está en el calendario")
    for k in ("hablante", "charla", "acento", "tema"):
        if not d.get("meta", {}).get(k):
            sys.exit(f"Falta meta.{k} en el descriptor")
    if not d.get("verified"):
        sys.exit("El clip no ha pasado `verify`.")
    c = cfg()
    dur = d["end"] - d["start"]
    if not c["clip_min_s"] <= dur <= c["clip_max_s"]:
        sys.exit(f"Dura {dur:.0f} s: tiene que estar entre {c['clip_min_s']} y {c['clip_max_s']} s.")
    bad = stress_problems(d["lines"])
    if bad:
        sys.exit(f"Sílabas tónicas mal marcadas (en una terminación átona): {bad}")
    if vocab_problems(d):
        sys.exit("; ".join(vocab_problems(d)))
    used = {x["fecha"] for x in cal["clips"]}
    if a.fecha:
        if a.fecha in used:
            sys.exit(f"El {a.fecha} ya tiene clip")
        fecha = a.fecha
    else:
        f = today()
        while f.isoformat() in used:
            f += dt.timedelta(days=1)
        fecha = f.isoformat()
    m = d["meta"]
    cal["clips"].append({"fecha": fecha, "slug": a.slug, "hablante": m["hablante"], "charla": m["charla"],
                         "acento": m["acento"], "tema": m["tema"], "duracion": round(d["end"] - d["start"])})
    cal["clips"].sort(key=lambda x: x["fecha"])
    jsave(CAL, cal)
    print(f"{a.slug} -> {fecha}")


def published(cal, hoy, retain_days):
    """Clips que se publican: los de los últimos `retain_days` días y todos los futuros."""
    desde = (hoy - dt.timedelta(days=retain_days)).isoformat()
    return [x for x in sorted(cal["clips"], key=lambda x: x["fecha"]) if x["fecha"] >= desde]


def cmd_site(a):
    c, cal, hoy = cfg(), jload(CAL), today()
    pub = published(cal, hoy, c["retain_days"])
    keep = {x["slug"] for x in pub}
    retirados = 0
    for f in glob.glob(os.path.join(SITE_CLIPS, "*")):
        if os.path.basename(f).rsplit(".", 1)[0] not in keep:
            os.remove(f); retirados += 1
    data = {"warn_days": c["warn_days"], "timezone": c["timezone"],
            "clips": [{k: x[k] for k in ("fecha", "slug", "hablante", "charla", "tema", "duracion")} for x in pub]}
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    s = open(INDEX, encoding="utf-8").read()
    s = re.sub(r"(<!-- DATA:START -->\n).*?(<!-- DATA:END -->)",
               lambda m: m.group(1) + '<script id="data" type="application/json">' + blob + "</script>\n" + m.group(2),
               s, flags=re.S)
    open(INDEX, "w", encoding="utf-8").write(s)
    print(f"site/index.html: {len(pub)} clips publicados" + (f" · {retirados} archivos antiguos retirados" if retirados else ""))


def cmd_status(a):
    cal, hoy = jload(CAL), today()
    cl = sorted(cal["clips"], key=lambda x: x["fecha"])
    cur = next((x for x in cl if x["fecha"] == hoy.isoformat()), None)
    fut = [x for x in cl if x["fecha"] > hoy.isoformat()]
    print(f"Hoy ({hoy}): {cur['slug'] if cur else 'SIN CLIP'}")
    print(f"Último día con clip: {cl[-1]['fecha'] if cl else '-'} · días que quedan después de hoy: {len(fut)}")
    if len(fut) < cfg()["warn_days"]:
        print("AVISO: hay que fabricar una tanda nueva (skill nueva-tanda).")
    voces = {}
    for x in cl[-31:]:
        voces[x["hablante"]] = voces.get(x["hablante"], 0) + 1
    print("Hablantes recientes:", ", ".join(f"{k} ×{v}" for k, v in voces.items()))


def problems():
    """Lista de problemas que impiden publicar (vacía si todo está bien)."""
    errs, c = [], cfg()
    cal = jload(CAL)
    cl = sorted(cal["clips"], key=lambda x: x["fecha"])
    fechas = [x["fecha"] for x in cl]
    if len(set(fechas)) != len(fechas):
        errs.append("Hay fechas repetidas en el calendario")
    if len({x["slug"] for x in cl}) != len(cl):
        errs.append("Hay clips repetidos en el calendario")
    if cl:
        d, fin = dt.date.fromisoformat(cl[0]["fecha"]), dt.date.fromisoformat(cl[-1]["fecha"])
        while d <= fin:
            if d.isoformat() not in fechas:
                errs.append(f"Día sin clip: {d}")
            d += dt.timedelta(days=1)
    for x in cl:
        p = desc_path(x["slug"])
        if not os.path.exists(p):
            errs.append(f"{x['slug']}: falta el descriptor"); continue
        dsc = jload(p)
        if not dsc.get("verified"):
            errs.append(f"{x['slug']}: sin verificar")
        if stress_problems(dsc.get("lines", [])):
            errs.append(f"{x['slug']}: sílabas tónicas mal marcadas {stress_problems(dsc['lines'])}")
        for pv in vocab_problems(dsc):
            errs.append(f"{x['slug']}: {pv}")
        if not c["clip_min_s"] - 5 <= x["duracion"] <= c["clip_max_s"] + 5:
            errs.append(f"{x['slug']}: dura {x['duracion']} s")
    m = re.search(r'<script id="data" type="application/json">(.*?)</script>', open(INDEX, encoding="utf-8").read(), re.S)
    pub = json.loads(m.group(1).replace("<\\/", "</"))["clips"] if m else []
    if not pub:
        errs.append("site/index.html no tiene clips: ejecuta `shadow.py site`")
    cal_by_slug = {x["slug"]: x for x in cl}
    for x in pub:
        if x["slug"] not in cal_by_slug or cal_by_slug[x["slug"]]["fecha"] != x["fecha"]:
            errs.append(f"{x['slug']}: la web no coincide con el calendario: ejecuta `shadow.py site`")
        for ext in ("mp3", "json"):
            if not os.path.exists(os.path.join(SITE_CLIPS, f"{x['slug']}.{ext}")):
                errs.append(f"{x['slug']}: falta site/clips/{x['slug']}.{ext}")
    return errs


def cmd_check(a):
    errs = problems()
    for e in errs:
        print("ERROR:", e)
    if errs:
        sys.exit(f"{len(errs)} problema(s): no se publica.")
    print("Todo correcto")


def main():
    import signal
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    for n in ("status", "site", "check"):
        sp.add_parser(n)
    sp.add_parser("download").add_argument("url")
    p = sp.add_parser("srt"); p.add_argument("id"); p.add_argument("desde", type=float, nargs="?"); p.add_argument("hasta", type=float, nargs="?")
    p = sp.add_parser("words"); p.add_argument("id"); p.add_argument("ini", type=float); p.add_argument("fin", type=float)
    for n in ("align", "build"):
        sp.add_parser(n).add_argument("slug")
    sp.add_parser("render").add_argument("slug", nargs="?")
    p = sp.add_parser("verify"); p.add_argument("slug"); p.add_argument("--force", action="store_true")
    p = sp.add_parser("add"); p.add_argument("slug"); p.add_argument("--fecha", help="AAAA-MM-DD")
    a = ap.parse_args()
    globals()["cmd_" + a.cmd](a)


if __name__ == "__main__":
    main()
