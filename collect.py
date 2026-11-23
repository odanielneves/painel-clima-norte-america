#!/usr/bin/env python3
"""Coleta temperatura diária e neve (Open-Meteo) e grava data/latest.json.

Guarda a série diária desde 1º de janeiro do ano anterior até ontem (UTC),
para o painel calcular qualquer janela (7 dias, quinzena, mês) e comparar
com o mesmo período do ano passado. Sem chave de API; só biblioteca padrão.
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# nome, país, estado/província, região, latitude, longitude
CITIES = [
    ("Buffalo", "EUA", "NY", "Snowbelt", 42.89, -78.88),
    ("Syracuse", "EUA", "NY", "Snowbelt", 43.05, -76.15),
    ("Chicago", "EUA", "IL", "Snowbelt", 41.88, -87.63),
    ("Minneapolis", "EUA", "MN", "Snowbelt", 44.98, -93.27),
    ("Detroit", "EUA", "MI", "Snowbelt", 42.33, -83.05),
    ("Boston", "EUA", "MA", "Snowbelt", 42.36, -71.06),
    ("Denver", "EUA", "CO", "Snowbelt", 39.74, -104.99),
    ("Salt Lake City", "EUA", "UT", "Snowbelt", 40.76, -111.89),
    ("Phoenix", "EUA", "AZ", "Sunbelt", 33.45, -112.07),
    ("Houston", "EUA", "TX", "Sunbelt", 29.76, -95.37),
    ("Dallas", "EUA", "TX", "Sunbelt", 32.78, -96.80),
    ("San Antonio", "EUA", "TX", "Sunbelt", 29.42, -98.49),
    ("Miami", "EUA", "FL", "Sunbelt", 25.76, -80.19),
    ("Tampa", "EUA", "FL", "Sunbelt", 27.95, -82.46),
    ("Atlanta", "EUA", "GA", "Sunbelt", 33.75, -84.39),
    ("Las Vegas", "EUA", "NV", "Sunbelt", 36.17, -115.14),
    ("Los Angeles", "EUA", "CA", "Sunbelt", 34.05, -118.24),
    ("Toronto", "Canadá", "ON", "—", 43.65, -79.38),
    ("Montreal", "Canadá", "QC", "—", 45.50, -73.57),
    ("Vancouver", "Canadá", "BC", "—", 49.28, -123.12),
    ("Calgary", "Canadá", "AB", "—", 51.05, -114.07),
    ("Cidade do México", "México", "CDMX", "—", 19.43, -99.13),
    ("Monterrey", "México", "NL", "—", 25.69, -100.32),
    ("Guadalajara", "México", "JAL", "—", 20.67, -103.35),
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


def fetch_city(name, pais, estado, regiao, lat, lon, today, dias):
    start = dias[0]
    cut = today - timedelta(days=8)  # o arquivo histórico tem atraso de alguns dias
    tmax, tmin = {}, {}

    if cut >= start:
        ar = get_json(ARCHIVE_URL, {
            "latitude": lat, "longitude": lon, "timezone": "UTC",
            "start_date": start.isoformat(), "end_date": cut.isoformat(),
            "daily": "temperature_2m_max,temperature_2m_min",
        })
        for d, a, b in zip(ar["daily"]["time"],
                           ar["daily"]["temperature_2m_max"],
                           ar["daily"]["temperature_2m_min"]):
            tmax[d], tmin[d] = a, b

    fc = get_json(FORECAST_URL, {
        "latitude": lat, "longitude": lon, "timezone": "UTC",
        "current": "temperature_2m,weather_code,snowfall",
        "daily": "temperature_2m_max,temperature_2m_min",
        "past_days": 8, "forecast_days": 1,
    })
    for d, a, b in zip(fc["daily"]["time"],
                       fc["daily"]["temperature_2m_max"],
                       fc["daily"]["temperature_2m_min"]):
        tmax[d], tmin[d] = a, b

    cur = fc.get("current", {})
    neve = (cur.get("weather_code") in SNOW_CODES) or ((cur.get("snowfall") or 0) > 0)

    return {
        "nome": name, "pais": pais, "estado": estado, "regiao": regiao,
        "ok": True, "neve": int(neve), "erro": None,
        "tmax": [tmax.get(d.isoformat()) for d in dias],
        "tmin": [tmin.get(d.isoformat()) for d in dias],
    }


def failed_row(name, pais, estado, regiao, exc, dias):
    return {
        "nome": name, "pais": pais, "estado": estado, "regiao": regiao,
        "ok": False, "neve": 0, "erro": str(exc),
        "tmax": [None] * len(dias), "tmin": [None] * len(dias),
    }


def main():
    today = datetime.now(timezone.utc).date()
    ultimo = today - timedelta(days=1)
    start = date(today.year - 1, 1, 1)
    dias = [start + timedelta(days=i) for i in range((ultimo - start).days + 1)]

    rows = []
    for name, pais, estado, regiao, lat, lon in CITIES:
        try:
            rows.append(fetch_city(name, pais, estado, regiao, lat, lon, today, dias))
            print(f"ok    {name}")
        except Exception as exc:
            rows.append(failed_row(name, pais, estado, regiao, exc, dias))
            print(f"falha {name}: {exc}", file=sys.stderr)
        time.sleep(0.3)  # gentileza com a API

    if not any(r["ok"] for r in rows):
        sys.exit("Nenhuma cidade foi coletada; mantendo o data/latest.json anterior.")

    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "hoje": today.isoformat(),
        "ultimo_dia": ultimo.isoformat(),
        "dias": [d.isoformat() for d in dias],
        "cidades": rows,
    }

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Gravado em {OUT_FILE}")


if __name__ == "__main__":
    main()
