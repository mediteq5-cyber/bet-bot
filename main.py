import os
import requests
import json
import time
from datetime import datetime, date
import pytz
from anthropic import Anthropic

# ── Configurações ─────────────────────────────────────────────────────────────
TELEGRAM_TOKEN    = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID  = os.environ.get("TELEGRAM_CHAT_ID", "")   # opcional: restringe acesso
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
FOOTBALL_API_KEY  = os.environ["FOOTBALL_API_KEY"]

TIMEZONE = pytz.timezone("America/Sao_Paulo")
client   = Anthropic(api_key=ANTHROPIC_API_KEY)

LEAGUES = {
    "PL":  "Premier League 🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    "BL1": "Bundesliga 🇩🇪",
    "PD":  "La Liga 🇪🇸",
    "SA":  "Serie A 🇮🇹",
    "FL1": "Ligue 1 🇫🇷",
    "CL":  "Champions League 🏆",
    "BSB": "Brasileirão 🇧🇷",
}

# ── Helpers Telegram ──────────────────────────────────────────────────────────
def tg(method: str, payload: dict) -> dict:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.json()
    except Exception as e:
        print(f"[ERRO] Telegram/{method}: {e}")
        return {}

def send(chat_id, text: str):
    tg("sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    })

def send_typing(chat_id):
    tg("sendChatAction", {"chat_id": chat_id, "action": "typing"})

# ── Busca jogos ───────────────────────────────────────────────────────────────
def get_matches(target_date: date) -> list:
    headers = {"X-Auth-Token": FOOTBALL_API_KEY}
    url = f"https://api.football-data.org/v4/matches?date={target_date.isoformat()}"
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[ERRO] Football API: {e}")
        return []

    matches = []
    for m in data.get("matches", []):
        code = m["competition"]["code"]
        if code not in LEAGUES:
            continue
        matches.append({
            "league":   LEAGUES[code],
            "home":     m["homeTeam"].get("shortName") or m["homeTeam"]["name"],
            "away":     m["awayTeam"].get("shortName") or m["awayTeam"]["name"],
            "time_utc": m["utcDate"],
        })
    return matches

def fmt_time(utc_str: str) -> str:
    try:
        dt = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
        return dt.astimezone(TIMEZONE).strftime("%H:%M")
    except Exception:
        return "--:--"

# ── Gera múltipla com Claude ──────────────────────────────────────────────────
def generate_tip(matches: list, style: str = "conservadora") -> dict:
    jogos = "\n".join(
        f"- {m['league']} | {m['home']} x {m['away']} as {fmt_time(m['time_utc'])} (BRT)"
        for m in matches
    )

    perfis = {
        "conservadora": "odd total entre 8x e 12x, apostas de baixo risco",
        "agressiva":    "odd total entre 15x e 25x, apostas de maior risco",
        "segura":       "odd total entre 4x e 7x, apenas favoritos claros",
    }
    perfil = perfis.get(style, perfis["conservadora"])

    prompt = f"""Voce e um analista esportivo especialista em apostas.

Data: {date.today().strftime('%d/%m/%Y')}
Estilo: {style} ({perfil})

Jogos disponíveis:
{jogos}

Monte uma MÚLTIPLA com 4 a 6 selecoes respeitando o estilo "{style}".
DIVERSIFIQUE os mercados — use pelo menos 3 tipos diferentes entre:
Resultado (1X2), Ambas marcam (BTTS), Over/Under gols, Over/Under escanteios, Vencedor 1a parte, Dupla hipótese.

Responda SOMENTE em JSON valido, sem markdown, sem texto extra:
{{
  "selecoes": [
    {{
      "jogo": "Time A x Time B",
      "liga": "Liga com emoji",
      "horario": "HH:MM",
      "mercado": "Nome do mercado",
      "aposta": "Descricao da aposta",
      "odd": 1.65,
      "motivo": "Breve justificativa"
    }}
  ],
  "odd_total": 10.5,
  "resumo": "Frase curta sobre o perfil da multipla"
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
        print(f"[ERRO] Claude: {e}")
        return None

# ── Monta mensagem ────────────────────────────────────────────────────────────
EMOJIS = {
    "resultado": "🏆", "1x2": "🏆",
    "ambas": "⚽", "btts": "⚽",
    "over": "📈", "under": "📉",
    "escanteio": "🚩", "corner": "🚩",
    "1ª parte": "⏱", "primeira": "⏱",
    "dupla": "🔀",
}

def market_emoji(m: str) -> str:
    ml = m.lower()
    for k, v in EMOJIS.items():
        if k in ml:
            return v
    return "🎯"

def build_message(tip: dict, style: str) -> str:
    icons = {"conservadora": "🛡", "agressiva": "🔥", "segura": "✅"}
    icon  = icons.get(style, "🎯")
    hoje  = date.today().strftime("%d/%m/%Y")

    lines = [
        f"{icon} <b>MÚLTIPLA {style.upper()} — {hoje}</b>",
        f"<i>{tip.get('resumo', '')}</i>",
        "",
    ]
    for s in tip["selecoes"]:
        e = market_emoji(s["mercado"])
        lines += [
            f"{e} <b>{s['jogo']}</b>",
            f"   🏷 {s['liga']}  ·  🕐 {s['horario']} (BRT)",
            f"   📌 <b>{s['mercado']}:</b> {s['aposta']}  —  <b>~{s['odd']}</b>",
            f"   💡 <i>{s['motivo']}</i>",
            "",
        ]
    lines += [
        "─────────────────────────",
        f"💰 <b>ODD TOTAL ESTIMADA: ~{tip['odd_total']}x</b>",
        "",
        "⚠️ <i>Odds estimadas. Confirme na sua casa antes de apostar. Jogue com responsabilidade.</i>",
    ]
    return "\n".join(lines)

# ── Handlers ──────────────────────────────────────────────────────────────────
HELP_TEXT = """🤖 <b>Bet Bot — Comandos</b>

/multipla — Múltipla conservadora (odd 8-12×)
/agressiva — Múltipla agressiva (odd 15-25×)
/segura — Múltipla segura (odd 4-7×)
/jogos — Lista os jogos disponíveis hoje
/ajuda — Exibe esta mensagem"""

def handle_jogos(chat_id):
    send_typing(chat_id)
    matches = get_matches(date.today())
    if not matches:
        send(chat_id, "📭 Nenhum jogo encontrado nas ligas monitoradas hoje.")
        return
    lines = [f"⚽ <b>Jogos de hoje — {date.today().strftime('%d/%m/%Y')}</b>\n"]
    for m in matches:
        lines.append(f"🕐 {fmt_time(m['time_utc'])}  {m['home']} × {m['away']}\n   {m['liga']}" if 'liga' in m else f"🕐 {fmt_time(m['time_utc'])}  {m['home']} × {m['away']}\n   {m['league']}")
    send(chat_id, "\n".join(lines))

def handle_multipla(chat_id, style="conservadora"):
    send_typing(chat_id)
    send(chat_id, "⏳ <i>Analisando os jogos de hoje, aguarde um momento...</i>")

    matches = get_matches(date.today())
    if not matches:
        send(chat_id, "📭 Nenhum jogo disponível hoje. Tente mais tarde ou em outro dia.")
        return

    send_typing(chat_id)
    tip = generate_tip(matches, style)
    if not tip:
        send(chat_id, "❌ Erro ao gerar a múltipla. Tente novamente em instantes.")
        return

    send(chat_id, build_message(tip, style))

# ── Controle de acesso ────────────────────────────────────────────────────────
ALLOWED_ID = TELEGRAM_CHAT_ID.strip() if TELEGRAM_CHAT_ID else ""

def is_allowed(chat_id) -> bool:
    if not ALLOWED_ID:          # vazio = aceita qualquer um
        return True
    return str(chat_id).strip() == ALLOWED_ID

def process_update(update: dict):
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return

    chat_id = msg["chat"]["id"]
    text = msg.get("text", "").strip().lower().split("@")[0]

    # Log sempre — mostra no Railway qual ID está tentando acessar
    print(f"[CMD] chat_id={chat_id}  ALLOWED_ID={ALLOWED_ID!r}  texto={text!r}")

    if not is_allowed(chat_id):
        print(f"[BLOQUEADO] {chat_id} != {ALLOWED_ID!r}")
        send(chat_id, f"⛔ Acesso não autorizado.\n\nSeu chat_id: <code>{chat_id}</code>")
        return

    if text == "/multipla":
        handle_multipla(chat_id, "conservadora")
    elif text == "/agressiva":
        handle_multipla(chat_id, "agressiva")
    elif text == "/segura":
        handle_multipla(chat_id, "segura")
    elif text == "/jogos":
        handle_jogos(chat_id)
    elif text in ("/start", "/ajuda", "/help"):
        send(chat_id, HELP_TEXT)
    else:
        send(chat_id, "❓ Comando não reconhecido.\n\n" + HELP_TEXT)

# ── Polling ───────────────────────────────────────────────────────────────────
def poll():
    print("[BOT] Iniciado — aguardando comandos no Telegram...")
    offset = None
    while True:
        try:
            params = {"timeout": 30, "allowed_updates": ["message"]}
            if offset:
                params["offset"] = offset
            resp = requests.get(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
                params=params,
                timeout=35,
            )
            for update in resp.json().get("result", []):
                offset = update["update_id"] + 1
                process_update(update)
        except Exception as e:
            print(f"[ERRO] Polling: {e}")
            time.sleep(5)

if __name__ == "__main__":
    poll()
