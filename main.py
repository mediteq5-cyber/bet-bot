import os
import requests
import schedule
import time
import json
from datetime import datetime, date
import pytz
from anthropic import Anthropic

# ── Configurações via variáveis de ambiente ──────────────────────────────────
TELEGRAM_TOKEN   = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
FOOTBALL_API_KEY  = os.environ["FOOTBALL_API_KEY"]   # football-data.org

TIMEZONE = pytz.timezone("America/Sao_Paulo")
SEND_TIME = "08:00"   # Horário de envio (BRT)

# Ligas monitoradas (football-data.org IDs)
LEAGUES = {
    "PL":  "Premier League 🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    "BL1": "Bundesliga 🇩🇪",
    "PD":  "La Liga 🇪🇸",
    "SA":  "Serie A 🇮🇹",
    "FL1": "Ligue 1 🇫🇷",
    "CL":  "Champions League 🏆",
    "BSB": "Brasileirão 🇧🇷",
}

client = Anthropic(api_key=ANTHROPIC_API_KEY)

# ── Busca jogos do dia ────────────────────────────────────────────────────────
def get_todays_matches() -> list[dict]:
    today = date.today().isoformat()
    headers = {"X-Auth-Token": FOOTBALL_API_KEY}
    url = f"https://api.football-data.org/v4/matches?date={today}"

    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[ERRO] Football API: {e}")
        return []

    matches = []
    for m in data.get("matches", []):
        competition_code = m["competition"]["code"]
        if competition_code not in LEAGUES:
            continue
        matches.append({
            "league":   LEAGUES[competition_code],
            "home":     m["homeTeam"]["shortName"] or m["homeTeam"]["name"],
            "away":     m["awayTeam"]["shortName"] or m["awayTeam"]["name"],
            "time_utc": m["utcDate"],
            "status":   m["status"],
        })

    return matches

# ── Formata horário para BRT ──────────────────────────────────────────────────
def fmt_time(utc_str: str) -> str:
    try:
        dt_utc = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
        dt_brt = dt_utc.astimezone(TIMEZONE)
        return dt_brt.strftime("%H:%M")
    except Exception:
        return "--:--"

# ── Gera múltipla com Claude ──────────────────────────────────────────────────
def generate_tip(matches: list[dict]) -> str:
    if not matches:
        return None

    jogos_texto = "\n".join(
        f"- {m['league']} | {m['home']} × {m['away']} às {fmt_time(m['time_utc'])} (BRT)"
        for m in matches
    )

    prompt = f"""Você é um analista esportivo especialista em apostas conservadoras.

Hoje são {date.today().strftime('%d/%m/%Y')} e os jogos disponíveis são:

{jogos_texto}

Sua tarefa:
1. Selecione entre 4 e 6 jogos para montar uma MÚLTIPLA CONSERVADORA com odd total entre 8x e 12x.
2. DIVERSIFIQUE os mercados: use pelo menos 3 mercados diferentes entre: Resultado (1X2), Ambas marcam (BTTS), Over/Under gols (ex: Over 2.5), Over/Under escanteios (ex: Over 9.5), Vencedor 1ª parte, Dupla hipótese (1X ou X2).
3. Para cada seleção, justifique brevemente (1 linha) o motivo.
4. Calcule a odd estimada total.

Responda SOMENTE em formato JSON válido, sem markdown ou texto extra:
{{
  "selecoes": [
    {{
      "jogo": "Time A × Time B",
      "liga": "Nome da liga com emoji",
      "horario": "HH:MM",
      "mercado": "Nome do mercado",
      "aposta": "Descrição da aposta",
      "odd": 1.65,
      "motivo": "Breve justificativa"
    }}
  ],
  "odd_total": 10.5,
  "resumo": "Frase curta descrevendo o perfil da múltipla"
}}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        # Remove possível bloco markdown residual
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except Exception as e:
        print(f"[ERRO] Claude API: {e}")
        return None

# ── Monta mensagem Telegram (HTML) ────────────────────────────────────────────
MARKET_EMOJI = {
    "resultado": "🏆", "1x2": "🏆",
    "ambas marcam": "⚽", "btts": "⚽",
    "over": "📈", "under": "📉",
    "escanteios": "🚩",
    "1ª parte": "⏱", "primeira parte": "⏱",
    "dupla": "🔀",
}

def market_emoji(mercado: str) -> str:
    m = mercado.lower()
    for k, v in MARKET_EMOJI.items():
        if k in m:
            return v
    return "🎯"

def build_message(tip: dict) -> str:
    hoje = date.today().strftime("%d/%m/%Y")
    selecoes = tip["selecoes"]
    odd_total = tip["odd_total"]
    resumo = tip.get("resumo", "")

    linhas = [
        f"🎰 <b>MÚLTIPLA DO DIA — {hoje}</b>",
        f"<i>{resumo}</i>",
        "",
    ]

    for i, s in enumerate(selecoes, 1):
        emoji = market_emoji(s["mercado"])
        linhas += [
            f"{emoji} <b>{s['jogo']}</b>",
            f"   🏷 {s['liga']}  ·  🕐 {s['horario']} (BRT)",
            f"   📌 <b>{s['mercado']}:</b> {s['aposta']}  →  <b>odd ~{s['odd']}</b>",
            f"   💡 <i>{s['motivo']}</i>",
            "",
        ]

    linhas += [
        "─────────────────────────",
        f"💰 <b>ODD TOTAL ESTIMADA: ~{odd_total}×</b>",
        "",
        "⚠️ <i>Odds estimadas. Confirme na sua casa antes de apostar. Jogue com responsabilidade.</i>",
    ]

    return "\n".join(linhas)

# ── Envia mensagem no Telegram ────────────────────────────────────────────────
def send_telegram(text: str) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        print(f"[OK] Mensagem enviada às {datetime.now(TIMEZONE).strftime('%H:%M:%S')}")
        return True
    except Exception as e:
        print(f"[ERRO] Telegram: {e}")
        return False

# ── Job diário ────────────────────────────────────────────────────────────────
def daily_job():
    print(f"\n[BOT] Executando job — {datetime.now(TIMEZONE).strftime('%d/%m/%Y %H:%M')}")

    matches = get_todays_matches()
    print(f"[BOT] {len(matches)} jogos encontrados nas ligas monitoradas")

    if not matches:
        send_telegram(
            "📭 <b>Múltipla do dia</b>\n\n"
            "Não encontrei jogos suficientes nas ligas monitoradas hoje. "
            "Voltamos amanhã! 🙌"
        )
        return

    tip = generate_tip(matches)
    if not tip:
        send_telegram("⚠️ Não foi possível gerar a múltipla hoje. Tente novamente mais tarde.")
        return

    msg = build_message(tip)
    send_telegram(msg)

# ── Agendamento (08:00 BRT = 11:00 UTC) ──────────────────────────────────────
if __name__ == "__main__":
    print(f"[BOT] Iniciado — envio diário às {SEND_TIME} BRT (11:00 UTC)")

    # Dispara imediatamente ao iniciar (útil pra testar)
    if os.environ.get("RUN_NOW") == "1":
        print("[BOT] RUN_NOW=1 detectado, enviando agora...")
        daily_job()

    schedule.every().day.at("11:00").do(daily_job)   # 11:00 UTC = 08:00 BRT

    while True:
        schedule.run_pending()
        time.sleep(30)
