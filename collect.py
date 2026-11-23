#!/usr/bin/env python3
"""Coleta temperatura e neve (Open-Meteo) e grava data/latest.json.

Janela: últimos 7 dias completos (UTC) vs. os mesmos dias do ano anterior.
Sem chave de API. Usa só a biblioteca padrão do Python.
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

CITIES = [
    # nome, país, região, latitude, longitude
    ("Buffalo", "EUA", "Snowbelt", 42.89, -78.88),
    ("Syracuse", "EUA", "Snowbelt", 43.05, -76.15),
    ("Chicago", "EUA", "Snowbelt", 41.88, -87.63),
    ("Minneapolis", "EUA", "Snowbelt", 44.98, -93.27),
    ("Detroit", "EUA", "Snowbelt", 42.33, -83.05),
    ("Boston", "EUA", "Snowbelt", 42.36, -71.06),
    ("Denver", "EUA", "Snowbelt", 39.74, -104.99),
    ("Salt Lake City", "EUA", "Snowbelt", 40.76, -111.89),
    ("Phoenix", "EUA", "Sunbelt", 33.45, -112.07),
    ("Houston", "EUA", "Sunbelt", 29.76, -95.37),
    ("Miami", "EUA", "Sunbelt", 25.76, -80.19),
    ("Dallas", "EUA", "Sunbelt", 32.78, -96.80),
    ("Atlanta", "EUA", "Sunbelt", 33.75, -84.39),
    ("Tampa", "EUA", "Sunbelt", 27.95, -82.46),
    ("San Antonio", "EUA", "Sunbelt", 29.42, -98.49),
    ("Las Vegas", "EUA", "Sunbelt", 36.17, -115.14),
    ("Los Angeles", "EUA", "Sunbelt", 34.05, -118.24),
    ("Toronto", "Canadá", "—", 43.65, -79.38),
    ("Montreal", "Canadá", "—", 45.50, -73.57),
    ("Vancouver", "Canadá", "—", 49.28, -123.12),
    ("Calgary", "Canadá", "—", 51.05, -114.07),
    ("Cidade do México", "México", "—", 19.43, -99.13),
    ("Monterrey", "México", "—", 25.69, -100.32),
    ("Guadalajara", "México", "—", 20.67, -103.35),
]

SNOW_CODES = {71, 73, 75, 77, 85, 86}  # códigos WMO de neve
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
OUT_FILE = Path(__file__).resolve().parent / "data" / "latest.json"


def get_json(url, params):
    full = f"{url}?{urllib.parse.urlencode(params)}"
    last_error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(full, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # rede ou resposta inválida: tenta de novo
            last_error = exc
            time.sleep(3 * (attempt + 1))
    raise last_error


def mean(values):
    vals = [v for v in values if v is not None]
    return round(sum(vals) / len(vals), 2) if vals else None


def delta(now, before):
    if now is None or before is None:
        return None
    return round(now - before, 1)


def fetch_city(name, country, region, lat, lon, today):
    start = today - timedelta(days=7)
    end = today - timedelta(days=1)
    ly_start = start - timedelta(days=365)
    ly_end = end - timedelta(days=365)

    fc = get_json(FORECAST_URL, {
        "latitude": lat,
        "longitude": lon,
        "timezone": "UTC",
        "current": "temperature_2m,weather_code,snowfall",
        "daily": "temperature_2m_max,temperature_2m_min",
        "past_days": 8,
        "forecast_days": 1,
    })
    days = [date.fromisoformat(d) for d in fc["daily"]["time"]]
    idx = [i for i, d in enumerate(days) if start <= d <= end]
    tmax_atual = mean([fc["daily"]["temperature_2m_max"][i] for i in idx])
    tmin_atual = mean([fc["daily"]["temperature_2m_min"][i] for i in idx])

    ar = get_json(ARCHIVE_URL, {
        "latitude": lat,
        "longitude": lon,
        "start_date": ly_start.isoformat(),
        "end_date": ly_end.isoformat(),
        "timezone": "UTC",
        "daily": "temperature_2m_max,temperature_2m_min",
    })
    tmax_ano = mean(ar["daily"]["temperature_2m_max"])
    tmin_ano = mean(ar["daily"]["temperature_2m_min"])

    cur = fc.get("current", {})
    neve = (cur.get("weather_code") in SNOW_CODES) or ((cur.get("snowfall") or 0) > 0)

    return {
        "nome": name,
        "pais": country,
        "regiao": region,
        "ok": True,
        "neve": int(neve),
        "tmax_atual": tmax_atual,
        "tmax_ano_passado": tmax_ano,
        "dmax": delta(tmax_atual, tmax_ano),
        "tmin_atual": tmin_atual,
        "tmin_ano_passado": tmin_ano,
        "dmin": delta(tmin_atual, tmin_ano),
        "erro": None,
    }


def failed_row(name, country, region, exc):
    return {
        "nome": name, "pais": country, "regiao": region, "ok": False,
        "neve": 0, "tmax_atual": None, "tmax_ano_passado": None, "dmax": None,
        "tmin_atual": None, "tmin_ano_passado": None, "dmin": None,
        "erro": str(exc),
    }


GROUPS = {
    "america_do_norte": lambda c: True,
    "eua": lambda c: c["pais"] == "EUA",
    "canada": lambda c: c["pais"] == "Canadá",
    "mexico": lambda c: c["pais"] == "México",
    "snowbelt": lambda c: c["regiao"] == "Snowbelt",
    "sunbelt": lambda c: c["regiao"] == "Sunbelt",
}


def summarize(rows):
    rows = [r for r in rows if r["ok"]]
    if not rows:
        return {"n": 0, "neve": 0}
    g = {
        "n": len(rows),
        "neve": sum(r["neve"] for r in rows),
    }
    for key in ("tmax_atual", "tmax_ano_passado", "tmin_atual", "tmin_ano_passado"):
        g[key] = mean([r[key] for r in rows])
    g["dmax"] = delta(g["tmax_atual"], g["tmax_ano_passado"])
    g["dmin"] = delta(g["tmin_atual"], g["tmin_ano_passado"])
    return g


def main():
    today = datetime.now(timezone.utc).date()
    rows = []
    for name, country, region, lat, lon in CITIES:
        try:
            rows.append(fetch_city(name, country, region, lat, lon, today))
            print(f"ok    {name}")
        except Exception as exc:
            rows.append(failed_row(name, country, region, exc))
            print(f"falha {name}: {exc}", file=sys.stderr)
        time.sleep(0.3)  # gentileza com a API

    if not any(r["ok"] for r in rows):
        sys.exit("Nenhuma cidade foi coletada; mantendo o data/latest.json anterior.")

    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "janela": {
            "atual": [(today - timedelta(days=7)).isoformat(), (today - timedelta(days=1)).isoformat()],
            "ano_passado": [
                (today - timedelta(days=372)).isoformat(),
                (today - timedelta(days=366)).isoformat(),
            ],
        },
        "cidades": rows,
        "grupos": {key: summarize([r for r in rows if pred(r)]) for key, pred in GROUPS.items()},
    }

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Gravado em {OUT_FILE}")


if __name__ == "__main__":
    main()
