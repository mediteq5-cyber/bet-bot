# 🎰 Bet Bot — Múltipla Diária no Telegram

Bot que gera automaticamente uma múltipla conservadora todo dia às **08h (BRT)** e envia direto no seu Telegram via IA (Claude).

---

## 📋 Pré-requisitos

| Item | Como obter | Custo |
|------|-----------|-------|
| **Bot Telegram** | @BotFather no Telegram | Grátis |
| **Chat ID** | Ver instruções abaixo | Grátis |
| **Anthropic API Key** | console.anthropic.com | ~$1-2/mês |
| **Football Data API** | football-data.org/client/register | Grátis |

---

## 🤖 Passo 1 — Criar o bot no Telegram

1. Abra o Telegram e procure por **@BotFather**
2. Envie `/newbot`
3. Escolha um nome (ex: `Minha Múltipla Bot`)
4. Escolha um username (ex: `minhamultipla_bot`)
5. Copie o **token** gerado (ex: `123456789:AAxxxxxxxx`)

**Descobrir seu Chat ID:**
1. Envie qualquer mensagem pro seu bot recém-criado
2. Acesse no navegador:
   ```
   https://api.telegram.org/bot<SEU_TOKEN>/getUpdates
   ```
3. Procure por `"id"` dentro de `"chat"` — esse é o seu Chat ID

---

## 🚀 Passo 2 — Deploy no Railway

### 2.1 Subir o código no GitHub
```bash
git init
git add .
git commit -m "feat: bet bot inicial"
# Crie um repositório no github.com e siga as instruções para push
git remote add origin https://github.com/SEU_USUARIO/bet-bot.git
git push -u origin main
```

### 2.2 Criar projeto no Railway
1. Acesse **railway.app** e faça login com GitHub
2. Clique em **New Project → Deploy from GitHub repo**
3. Selecione o repositório `bet-bot`
4. Railway vai detectar o `Procfile` automaticamente

### 2.3 Configurar variáveis de ambiente
No Railway, vá em **Variables** e adicione:

| Variável | Valor |
|----------|-------|
| `TELEGRAM_BOT_TOKEN` | Token do @BotFather |
| `TELEGRAM_CHAT_ID` | Seu Chat ID |
| `ANTHROPIC_API_KEY` | Chave em console.anthropic.com |
| `FOOTBALL_API_KEY` | Chave em football-data.org |
| `RUN_NOW` | `0` (deixe `1` só pra testar) |

4. Clique em **Deploy** — pronto! 🎉

---

## 🧪 Testando localmente

```bash
# Instalar dependências
pip install -r requirements.txt

# Copiar e preencher o .env
cp .env.example .env
# Edite o .env com seus valores reais

# Rodar com envio imediato
RUN_NOW=1 python main.py
```

---

## ⚽ Ligas monitoradas

- 🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League
- 🇩🇪 Bundesliga
- 🇪🇸 La Liga
- 🇮🇹 Serie A
- 🇫🇷 Ligue 1
- 🏆 Champions League
- 🇧🇷 Brasileirão

> O plano gratuito da football-data.org cobre Premier League, Bundesliga, La Liga, Serie A, Ligue 1 e Champions League.
> Para Brasileirão é necessário o plano pago (~€3/mês) ou trocar por outra API.

---

## 💬 Exemplo de mensagem enviada

```
🎰 MÚLTIPLA DO DIA — 18/04/2026
Múltipla conservadora diversificada, odd ~10x

🏆 Leeds United × Wolverhampton
   🏷 Premier League 🏴󠁧󠁢󠁥󠁮󠁧󠁿  ·  🕐 11:00 (BRT)
   📌 Resultado 1X2: Leeds vence  →  odd ~1.65
   💡 Leeds 60% favorito em casa, Wolves péssimo visitante

⚽ Brentford × Fulham
   🏷 Premier League 🏴󠁧󠁢󠁥󠁮󠁧󠁿  ·  🕐 08:30 (BRT)
   📌 Ambas marcam: Sim  →  odd ~1.65
   💡 Ambos marcam com regularidade nesta temporada
...

─────────────────────────
💰 ODD TOTAL ESTIMADA: ~10.5×
```

---

## ⚠️ Aviso

Este bot é apenas para entretenimento e fins informativos.
Aposte com responsabilidade. Nunca aposte mais do que pode perder.
