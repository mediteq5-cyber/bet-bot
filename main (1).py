import os
import requests
import json
import logging
from datetime import datetime, date
import pytz
from anthropic import Anthropic

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
    datefmt="%d/%m/%Y %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Configurações ─────────────────────────────────────────────────────────────
TELEGRAM_TOKEN    = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID  = os.environ.get("TELEGRAM_CHAT_ID", "")   # Opcional: restringir acesso
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
FOOTBALL_API_KEY  = os.environ["FOOTBALL_API_KEY"]

TIMEZONE = pytz.timezone("America/Sao_Paulo")

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

# ── Telegram helpers ──────────────────────────────────────────────────────────
def send_message(chat_id, text: str, parse_mode: str = "HTML") -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        return True
    except Exception as e:
        log.error(f"Erro ao enviar mensagem: {e}")
        return False

def send_typing(chat_id):
    """Mostra 'digitando...' enquanto processa."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendChatAction"
    try:
        requests.post(url, json={"chat_id": chat_id, "action": "typing"}, timeout=5)
    except Exception:
        pass

def get_updates(offset: int = 0) -> list:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    try:
        r = requests.get(url, params={"offset": offset, "timeout": 30}, timeout=35)
        r.raise_for_status()
        return r.json().get("result", [])
    except Exception as e:
        log.error(f"Erro ao buscar updates: {e}")
        return []

# ── Dados de futebol ──────────────────────────────────────────────────────────
def get_matches(target_date: date) -> list:
    headers = {"X-Auth-Token": FOOTBALL_API_KEY}
    url = f"https://api.football-data.org/v4/matches?date={target_date.isoformat()}"
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        log.error(f"Football API erro: {e}")
        return []

    matches = []
    for m in data.get("matches", []):
        code = m["competition"]["code"]
        if code not in LEAGUES:
            continue
        matches.append({
            "league":   LEAGUES[code],
            "home":     m["homeTeam"]["shortName"] or m["homeTeam"]["name"],
            "away":     m["awayTeam"]["shortName"] or m["awayTeam"]["name"],
            "time_utc": m["utcDate"],
        })
    return matches

def fmt_time(utc_str: str) -> str:
    try:
        dt = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
        return dt.astimezone(TIMEZONE).strftime("%H:%M")
    except Exception:
        return "--:--"

# ── Geração de tips com Claude ────────────────────────────────────────────────
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

def generate_tip(matches: list, odd_range: str = "entre 8x e 12x") -> dict:
    jogos = "\n".join(
        f"- {m['league']} | {m['home']} × {m['away']} às {fmt_time(m['time_utc'])} (BRT)"
        for m in matches
    )
    prompt = f"""Você é um analista esportivo especialista em apostas conservadoras.

Data: {date.today().strftime('%d/%m/%Y')}
Jogos disponíveis:
{jogos}

Monte uma MÚLTIPLA CONSERVADORA com odd total {odd_range}.
Use entre 4 e 6 jogos e DIVERSIFIQUE os mercados (mínimo 3 diferentes):
Resultado (1X2), Ambas marcam (BTTS), Over/Under gols, Over/Under escanteios, Vence 1ª parte, Dupla hipótese.

Responda SOMENTE JSON válido, sem markdown:
{{
  "selecoes": [
    {{
      "jogo": "Time A × Time B",
      "liga": "Liga com emoji",
      "horario": "HH:MM",
      "mercado": "Nome do mercado",
      "aposta": "Descrição da aposta",
      "odd": 1.65,
      "motivo": "Breve justificativa"
    }}
  ],
  "odd_total": 10.5,
  "resumo": "Frase curta sobre o perfil da múltipla"
}}"""

    try:
        resp = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = resp.content[0].text.strip().replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except Exception as e:
        log.error(f"Claude erro: {e}")
        return None

def build_message(tip: dict, target_date: date) -> str:
    hoje = target_date.strftime("%d/%m/%Y")
    linhas = [
        f"🎰 <b>MÚLTIPLA — {hoje}</b>",
        f"<i>{tip.get('resumo', '')}</i>",
        "",
    ]
    for s in tip["selecoes"]:
        emoji = market_emoji(s["mercado"])
        linhas += [
            f"{emoji} <b>{s['jogo']}</b>",
            f"   🏷 {s['liga']}  ·  🕐 {s['horario']} (BRT)",
            f"   📌 <b>{s['mercado']}:</b> {s['aposta']}  →  <b>~{s['odd']}</b>",
            f"   💡 <i>{s['motivo']}</i>",
            "",
        ]
    linhas += [
        "─────────────────────────",
        f"💰 <b>ODD TOTAL ESTIMADA: ~{tip['odd_total']}×</b>",
        "",
        "⚠️ <i>Odds estimadas. Confirme na sua casa antes de apostar.</i>",
    ]
    return "\n".join(linhas)

# ── Handlers de comando ───────────────────────────────────────────────────────
def handle_start(chat_id, first_name: str):
    send_message(chat_id,
        f"👋 Olá, <b>{first_name}</b>! Bem-vindo ao <b>Bet Bot</b> 🎰\n\n"
        "Comandos disponíveis:\n\n"
        "📌 /multipla — Múltipla conservadora de <b>hoje</b> (~10x)\n"
        "📌 /amanha — Múltipla para <b>amanhã</b> (~10x)\n"
        "📌 /alta — Múltipla arrojada (~15x)\n"
        "📌 /baixa — Múltipla ultra conservadora (~5x)\n"
        "📌 /ajuda — Mostra esta mensagem\n\n"
        "⚠️ <i>Jogue com responsabilidade.</i>"
    )

def handle_multipla(chat_id, target_date: date, odd_range: str = "entre 8x e 12x", label: str = ""):
    send_typing(chat_id)
    send_message(chat_id, "⏳ <i>Buscando jogos e gerando sua múltipla... aguarde!</i>")
    send_typing(chat_id)

    matches = get_matches(target_date)
    if not matches:
        send_message(chat_id,
            "📭 <b>Nenhum jogo encontrado</b>\n\n"
            "Não há jogos nas ligas monitoradas para essa data. Tente outro dia!"
        )
        return

    tip = generate_tip(matches, odd_range)
    if not tip:
        send_message(chat_id, "❌ Não foi possível gerar a múltipla agora. Tente novamente em instantes.")
        return

    msg = build_message(tip, target_date)
    if label:
        msg = f"<b>{label}</b>\n\n" + msg
    send_message(chat_id, msg)
    log.info(f"Múltipla enviada para chat_id={chat_id} | odd={tip['odd_total']}")

def handle_unknown(chat_id):
    send_message(chat_id,
        "❓ Comando não reconhecido.\n\n"
        "Use /ajuda para ver os comandos disponíveis."
    )

# ── Verificação de acesso ─────────────────────────────────────────────────────
def is_allowed(chat_id) -> bool:
    if not TELEGRAM_CHAT_ID:
        return True
    allowed = [x.strip() for x in TELEGRAM_CHAT_ID.split(",")]
    return str(chat_id) in allowed

# ── Loop principal (long polling) ─────────────────────────────────────────────
def run():
    log.info("🤖 Bet Bot iniciado — aguardando comandos no Telegram...")
    offset = 0

    while True:
        updates = get_updates(offset)
        for update in updates:
            offset = update["update_id"] + 1
            message = update.get("message") or update.get("edited_message")
            if not message:
                continue

            chat_id    = message["chat"]["id"]
            first_name = message.get("from", {}).get("first_name", "usuário")
            text       = message.get("text", "").strip()

            if not text.startswith("/"):
                continue

            if not is_allowed(chat_id):
                send_message(chat_id, "⛔ Acesso não autorizado.")
                log.warning(f"Acesso negado para chat_id={chat_id}")
                continue

            cmd = text.split()[0].lower().split("@")[0]
            log.info(f"Comando: {cmd} | chat_id={chat_id} | usuário={first_name}")

            today    = datetime.now(TIMEZONE).date()
            tomorrow = date.fromordinal(today.toordinal() + 1)

            if cmd in ("/start", "/ajuda"):
                handle_start(chat_id, first_name)

            elif cmd == "/multipla":
                handle_multipla(chat_id, today)

            elif cmd == "/amanha":
                handle_multipla(chat_id, tomorrow, label="📅 Múltipla de amanhã")

            elif cmd == "/alta":
                handle_multipla(chat_id, today, odd_range="entre 14x e 18x", label="🔥 Múltipla ARROJADA")

            elif cmd == "/baixa":
                handle_multipla(chat_id, today, odd_range="entre 3x e 6x", label="🛡 Múltipla ULTRA CONSERVADORA")

            else:
                handle_unknown(chat_id)

if __name__ == "__main__":
    run()
