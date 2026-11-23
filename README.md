# Painel de clima — América do Norte

Painel web que compara a temperatura dos últimos 7 dias com o mesmo período do ano anterior, e mostra onde está nevando. Atualiza sozinho a cada hora.

## Como funciona

1. `collect.py` consulta a API pública da Open-Meteo (sem chave) e grava `data/latest.json`.
2. `.github/workflows/atualizar.yml` roda o script a cada hora pelo GitHub Actions e faz commit do JSON quando há mudança.
3. `index.html` lê `data/latest.json` e desenha o painel. Hospedado pelo GitHub Pages.

## Editar as cidades

Em `collect.py`, na lista `CITIES`: nome, país, região (`Snowbelt`, `Sunbelt` ou `—`), latitude e longitude.

## Rodar manualmente

```bash
python collect.py
```

Ou, no GitHub, aba **Actions** → **Atualizar dados de clima** → **Run workflow**.
