"""Pruebas de tools/shadow.py. Se ejecutan en GitHub antes de publicar: python -m pytest -q tests

No necesitan red, ni Whisper, ni ffmpeg: prueban la lógica (texto, alineado, calendario, web y comprobaciones).
"""
import datetime as dt
import importlib
import json
import os
import shutil
import sys
import types

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def S(tmp_path, monkeypatch):
    """Carga shadow.py apuntando a un repo de prueba vacío (con la config y la portada reales)."""
    for d in ("data/clips", "site/clips"):
        (tmp_path / d).mkdir(parents=True)
    shutil.copy(os.path.join(REPO, "config.json"), tmp_path / "config.json")
    shutil.copy(os.path.join(REPO, "site", "index.html"), tmp_path / "site" / "index.html")
    (tmp_path / "data" / "calendario.json").write_text('{"clips": []}')
    monkeypatch.setenv("SHADOW_ROOT", str(tmp_path))
    sys.path.insert(0, os.path.join(REPO, "tools"))
    mod = importlib.reload(importlib.import_module("shadow"))
    monkeypatch.setattr(mod, "today", lambda: dt.date(2026, 11, 10))
    yield mod
    sys.path.remove(os.path.join(REPO, "tools"))


def make_clip(S, slug, verified=True, dur=80):
    d = {"slug": slug, "video_id": "ted-x", "title": "T", "source": "TED", "url": "https://www.ted.com/talks/x",
         "start": 100.0, "end": 100.0 + dur, "lines": ["Hello <b>world</b>."],
         "cues": [{"s": 100.0, "e": 100.0 + dur, "t": "Hello <b>world</b>."}],
         "meta": {"hablante": "A B", "charla": "C", "acento": "Americano general", "tema": "Tema"}}
    if verified:
        d["verified"] = "2026-11-01"
    S.jsave(S.desc_path(slug), d)
    for ext in ("mp3", "json"):
        open(os.path.join(S.SITE_CLIPS, f"{slug}.{ext}"), "w").write("x")


def args(**kw):
    return types.SimpleNamespace(**kw)


# ---------------------------------------------------------------- texto
def test_plain_tokens_quita_marcas_y_separa_cifras(S):
    assert S.plain_tokens("We <b>be</b>lieve / in 30,000 days —") == ["We", "believe", "in", "30", "000", "days"]


def test_srt_corrige_formato_ted(S, tmp_path):
    p = tmp_path / "a.en.srt"
    p.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello there.\n\n"
                 "2\n00:00:03,000 --> 00:00:05,000\nFirst. 00:00:05.500 -- 00:00:07.000 Second.\n")
    assert S.srt_entries(str(p)) == [(1.0, 2.0, "Hello there."), (3.0, 5.0, "First."), (5.5, 7.0, "Second.")]


def test_align_asigna_tiempos_a_cada_linea(S):
    d = {"start": 10.0, "end": 14.0, "lines": ["One <b>two</b>", "three / four"]}
    words = [(10.0, 10.4, "One"), (10.5, 10.9, "two"), (12.0, 12.4, "three"), (12.5, 13.0, "four")]
    cues, start, end, missing = S.align(d, words)
    assert missing == []
    assert cues[0]["s"] == pytest.approx(9.88) and cues[1]["s"] == pytest.approx(11.88)
    assert cues[0]["e"] == cues[1]["s"]


def test_detecta_tonicas_en_terminaciones_atonas(S):
    assert S.stress_problems(["ask<b>ing</b> about the <b>ques</b>tion", "ques<b>tion</b>s"]) == ["k<b>ing</b>"]
    assert S.stress_problems(["<b>ask</b>ing about <b>ques</b>tions, <b>ev</b>erything"]) == []


def test_add_rechaza_duracion_fuera_de_rango_y_tonicas_mal_marcadas(S):
    make_clip(S, "corto", dur=40)
    with pytest.raises(SystemExit):
        S.cmd_add(args(slug="corto", fecha=None))
    make_clip(S, "mal")
    d = S.jload(S.desc_path("mal")); d["lines"] = ["they were ask<b>ing</b>"]; S.jsave(S.desc_path("mal"), d)
    with pytest.raises(SystemExit):
        S.cmd_add(args(slug="mal", fecha=None))


def test_compare_detecta_palabras_que_faltan(S):
    cues = [{"s": 0.0, "e": 2.0, "t": "hello big world"}]
    missing, extra, bad = S.compare(cues, [(0.1, 0.3, "hello"), (0.5, 0.9, "world")], 0)
    assert missing == ["big"] and extra == [] and bad == []


def test_clip_data_tiempos_relativos_al_mp3(S):
    d = {"title": "T", "source": "TED", "url": "u", "start": 100.0, "end": 160.0,
         "cues": [{"s": 100.0, "e": 105.0, "t": "x"}]}
    out = S.clip_data(d)
    assert out["cues"][0]["s"] == pytest.approx(0.4) and out["segment"] == "01:40–02:40 (60 s)"


# ---------------------------------------------------------------- calendario
def test_add_usa_el_primer_dia_libre(S):
    make_clip(S, "a"); make_clip(S, "b")
    S.cmd_add(args(slug="a", fecha=None)); S.cmd_add(args(slug="b", fecha=None))
    assert [x["fecha"] for x in S.jload(S.CAL)["clips"]] == ["2026-11-10", "2026-11-11"]


def test_add_rechaza_sin_verificar_y_fechas_repetidas(S):
    make_clip(S, "a", verified=False)
    with pytest.raises(SystemExit):
        S.cmd_add(args(slug="a", fecha=None))
    make_clip(S, "b"); make_clip(S, "c")
    S.cmd_add(args(slug="b", fecha="2026-11-20"))
    with pytest.raises(SystemExit):
        S.cmd_add(args(slug="c", fecha="2026-11-20"))


# ---------------------------------------------------------------- web y comprobaciones
def test_site_publica_y_retira_clips_antiguos(S):
    for i, f in enumerate(["2026-08-01", "2026-11-09", "2026-11-10", "2026-11-11"]):
        make_clip(S, f"c{i}")
        S.cmd_add(args(slug=f"c{i}", fecha=f))
    S.cmd_site(args())
    html = open(S.INDEX, encoding="utf-8").read()
    assert '"c0"' not in html and '"c3"' in html
    assert not os.path.exists(os.path.join(S.SITE_CLIPS, "c0.mp3"))
    assert os.path.exists(os.path.join(S.SITE_CLIPS, "c3.mp3"))


def test_check_pasa_si_todo_cuadra(S):
    for i in range(3):
        make_clip(S, f"c{i}")
        S.cmd_add(args(slug=f"c{i}", fecha=None))
    S.cmd_site(args())
    assert S.problems() == []


def test_check_detecta_huecos_y_archivos_que_faltan(S):
    make_clip(S, "a"); make_clip(S, "b")
    S.cmd_add(args(slug="a", fecha="2026-11-10")); S.cmd_add(args(slug="b", fecha="2026-11-12"))
    S.cmd_site(args())
    os.remove(os.path.join(S.SITE_CLIPS, "b.mp3"))
    errs = S.problems()
    assert any("Día sin clip: 2026-11-11" in e for e in errs)
    assert any("falta site/clips/b.mp3" in e for e in errs)


def test_el_repo_real_esta_listo_para_publicar():
    """El contenido real del repo pasa la comprobación completa."""
    sys.path.insert(0, os.path.join(REPO, "tools"))
    os.environ.pop("SHADOW_ROOT", None)
    mod = importlib.reload(importlib.import_module("shadow"))
    assert mod.problems() == []
