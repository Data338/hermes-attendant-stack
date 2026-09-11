---
name: hermes-whatsapp-attendant
description: >-
  Guia de campo para colocar um atendente WhatsApp no ar com Hermes usando a
  Cloud API OFICIAL da Meta + Cloudflare Tunnel, e para ensinar pessoas a
  navegar esses dois ecossistemas sem sofrer. Use quando precisar configurar
  webhook da Meta, inscrever app na WABA, criar/migrar tunnel Cloudflare,
  diagnosticar "mensagem não chega", "bot não responde", ou explicar a
  diferença entre Baileys e Cloud API. Inclui todos os gotchas que custaram
  horas de debug.
---

# Atendente WhatsApp: Meta Cloud API + Cloudflare Tunnel + Hermes

Playbook destilado de uma migração real (Baileys → Cloud API oficial) que
sofreu TODOS os erros possíveis, para a próxima pessoa não sofrer. Serve tanto
para **executar** quanto para **ensinar** alguém a navegar o ecossistema.

Regra de ouro: **nada chega no seu bot até as 3 coisas estarem verdadeiras ao
mesmo tempo** — (1) webhook verificado, (2) campo `messages` assinado, (3) o
App inscrito NA WABA. Faltando qualquer uma, o sintoma é o mesmo: silêncio.

---

## Parte 1 — Entendendo a hierarquia da Meta (decore isso)

```
Business Portfolio (conta de negócio)
└── WABA (WhatsApp Business Account)      ← ID 15-16 dígitos
    └── Phone Number (Phone Number ID)    ← o número que atende
App (developers.facebook.com)             ← a "aplicação" que recebe webhooks
System User (opcional, no Business)       ← dono do token permanente
```

- **WABA ≠ App.** São objetos diferentes e ambos importam.
- Uma pessoa pode ter VÁRIAS WABAs (uma vazia, uma de teste, a "de verdade").
  **Confira o ID antes de configurar** — é o erro nº 1. Abra
  `WhatsApp Manager` e veja qual WABA está selecionada no seletor do topo.
- **Token:** prefira um **System User** com `whatsapp_business_messaging` — gera
  token de longa duração (60d, renovável). Token de usuário humano expira e
  quebra em produção.

### Onde clicar (UI da Meta)

| O quê | URL |
|---|---|
| App / produtos | `https://developers.facebook.com/apps/<APP_ID>/` |
| Webhooks do App | `https://developers.facebook.com/apps/<APP_ID>/webhooks/` |
| Config do WhatsApp | `https://developers.facebook.com/apps/<APP_ID>/whatsapp-business/wa-settings/` |
| WhatsApp Manager (WABA/templates) | `https://business.facebook.com/latest/whatsapp_manager/message_templates/` |

---

## Parte 2 — Encanamento do webhook (o passo que **sempre** falha)

A infra toda (tunnel + listener) pode estar perfeita e **ainda assim nada
chega**, porque o webhook tem **3 travas independentes**:

### Trava 1 — Verify and save (handshake GET)
No App > Webhooks > produto **Whatsapp Business Account** (NÃO "User"):
- Callback URL: `https://SEU_HOST/whatsapp/webhook`
- Verify token: a mesma string que você pôs em `WHATSAPP_CLOUD_VERIFY_TOKEN`
- Clique **Verify and save**. Ele faz um GET com `hub.challenge`; seu servidor
  precisa devolver o challenge em texto puro (200). Se der erro, o tunnel ou o
  token estão errados.

### Trava 2 — Assinar os campos (Subscribe)
Na MESMA tela, na lista de **Webhook fields**, ligue `Subscribe` em:
- **`messages`** — obrigatório, sem ele não entra mensagem.
- `message_template_status_update`, `phone_number_quality_update` — úteis.
- Campos de coexistência (`message_echoes`, `smb_message_echoes`,
  `smb_app_state_sync`, `history`) — só existem para contas elegíveis
  (Tech Provider/BSP). Se der "Failed to subscribe", **ignore**, não quebra nada.

### Trava 3 — Inscrever o App NA WABA (a mais traiçoeira)
Fazer Verify+Subscribe **não** inscreve o App na WABA. Sem isso o webhook fica
"verificado" e mesmo assim **nenhum evento é entregue**. Confira e corrija via
Graph API (com o access token):

```bash
TOKEN="<access_token>"
WABA="<waba_id>"

# VER (vazio [] = não inscrito = nada chega)
curl -s "https://graph.facebook.com/v21.0/$WABA/subscribed_apps?access_token=$TOKEN"

# INSCREVER
curl -s -X POST "https://graph.facebook.com/v21.0/$WABA/subscribed_apps" \
  -d "subscribed_fields=messages" -d "access_token=$TOKEN"
# -> {"success":true}
```

> **Sintoma desta falha:** POST do webhook responde 200 no seu servidor, log
> limpo, zero mensagem. Você jura que é o app "unpublished". Não é.

### App "Unpublished" — o que realmente significa
O aviso vermelho *"Apps will only be able to receive test webhooks... unless
the app has been published"* **não bloqueia** o número de teste. Em modo dev,
mensagens do número de teste / admins / developers / testers SÃO entregues.
Produção geral só após publicar. Não perca horas achando que é isso.

---

## Parte 3 — Cloudflare Tunnel (por que e como)

**Por que:** a maioria das casas/escritórios está atrás de CGNAT — não há IP
público nem como abrir porta. O tunnel faz uma conexão **outbound-only** da sua
máquina até a borda da Cloudflare, e a Cloudflare publica um hostname HTTPS
apontando pra `localhost:<porta>` da sua máquina. Sem abrir porta, sem IP fixo.

### Quick tunnel vs Named tunnel

| | Quick (`cloudflared tunnel --url http://localhost:8090`) | Named (token) |
|---|---|---|
| URL | **aleatória, muda a cada boot** | **fixa** |
| Config | nenhuma | dashboard |
| Uso | teste rápido | **produção** |

> Quick tunnel é armadilha em produção: a cada reboot/queda de energia a URL
> muda e o webhook da Meta fica apontando pro host morto. **Use sempre named.**

### Criar o named tunnel (evite o fluxo `argotunnel`)
`cloudflared tunnel login` (fluxo `dash.cloudflare.com/argotunnel`) tem um
**bug** com contas de nome longo: tenta criar um token com nome >120 chars e
falha com *"name must have a length between 1 and 120"*, ou o navegador baixa
o `cert.pem` em vez de entregar. **Não use.** Vá de Zero Trust:

1. `https://one.dash.cloudflare.com/<ACCOUNT_ID>/networks/tunnels`
   (ou menu **Protect & connect > Networks > Tunnels**)
2. **Create a tunnel > Cloudflared**, dê um nome (ex: `IaraWhatsappAtendimento`)
3. Copie o **token** da tela do conector

### A rota pública: aba CERTA
Dentro do túnel, use **Published application routes** (a que publica na
Internet com HTTPS e cria o DNS sozinho):
- Subdomain + Domain → `wpp.seudominio.com.br`
- **Path: DEIXE VAZIO** (aquele campo é regex de caminho URL, não endereço!)
- Service: Type `HTTP`, URL `localhost:8090`

> **ARMADILHA:** a aba **Hostname routes** parece a mesma coisa, mas é rota
> **privada** (exige WARP/One Client na ponta). A Meta nunca alcança. Se você
> salvou lá, apareceu um aviso azul *"requires traffic to pass via Cloudflare
> Gateway"* — é o sinal de que você está na tela errada.

### Rodar como serviço perene (systemd --user)

Token em arquivo com permissão 600 (nunca no `ExecStart` cru — a variável não
expande e o serviço morre com `flag needs an argument: -token`):

```bash
printf '%s' '<TUNNEL_TOKEN>' > ~/.cloudflared-wpp-token && chmod 600 ~/.cloudflared-wpp-token
```

`~/.config/systemd/user/cloudflared-wpp.service`:
```ini
[Unit]
Description=Cloudflare named tunnel -> localhost:8090
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/usr/local/bin/cloudflared tunnel --no-autoupdate run --token-file %h/.cloudflared-wpp-token
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now cloudflared-wpp.service
sudo loginctl enable-linger "$USER"   # sobrevive a logout/reboot
```

Conferir sucesso nos logs: `Registered tunnel connection` (aparece na conexão;
depois fica quieto — ausência de novas linhas NÃO é erro).

---

## Parte 4 — Especificidades do gateway Hermes

Vars do adapter Cloud (o prefixo é `WHATSAPP_CLOUD_`, distinto do Baileys):
`VERIFY_TOKEN`, `WEBHOOK_PORT`, `WEBHOOK_PATH`, `PHONE_NUMBER_ID`, `APP_ID`,
`APP_SECRET`, `WABA_ID`, `ACCESS_TOKEN`.

O adapter auto-ativa quando vê `PHONE_NUMBER_ID` + `ACCESS_TOKEN`.

### 🚨 O gotcha que causa "bot mudo" (drop silencioso)

O adapter **Cloud** ignora `WHATSAPP_ALLOWED_USERS`. Ele usa política própria:
`WHATSAPP_CLOUD_ALLOW_ALL_USERS` (ou `WHATSAPP_CLOUD_ALLOWED_USERS`). Sem uma
das duas, **toda DM é descartada silenciosamente**: o POST retorna 200, o log
fica limpo, nenhuma sessão é criada. Parece que o webhook não funciona.

```
# Correção (no compose E no .env do volume — o plugin lê os dois):
WHATSAPP_CLOUD_ALLOW_ALL_USERS=true
```

### Modo único por número
Não rode Baileys e Cloud no MESMO número ao mesmo tempo. Sete
`WHATSAPP_ENABLED=false` quando o Cloud está ativo, senão os dois adapters
brigam pelo número.

### Suprimir mensagens "stock" do Hermes
Sem patch, o Hermes vaza avisos internos pro cliente (`sethome`, credits/usage,
whitelist). O `patches.py` deste repo transforma `_deliver_platform_notice` em
no-op para **`Platform.WHATSAPP` E `Platform.WHATSAPP_CLOUD`** (são enums
diferentes — esquecer o `_CLOUD` deixa o problema vivo no Cloud API).

### "Sethome" / canal
`gateway_state.json` com `channel directory built: 0 target(s)` + `connected` é
**saudável quando ocioso** — não é erro. O aviso "run /sethome first" só aparece
em recursos que exigem home channel (handoff, cron delivery).

---

## Parte 5 — Runbook de verificação (nessa ordem)

```bash
# 1. Túnel vivo e registrado
systemctl --user is-active cloudflared-wpp.service
journalctl --user -u cloudflared-wpp.service --no-pager | grep -c "Registered tunnel connection"

# 2. Handshake público responde o challenge (troque host/token)
curl -s "https://wpp.seudominio.com.br/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=<TOKEN>&hub.challenge=12345"
# -> 12345

# 3. App inscrito na WABA (deve listar o app, não [])
curl -s "https://graph.facebook.com/v21.0/<WABA_ID>/subscribed_apps?access_token=<TOKEN>"

# 4. Token/número válidos
curl -s "https://graph.facebook.com/v21.0/<PHONE_NUMBER_ID>?fields=display_phone_number,verified_name,quality_rating&access_token=<TOKEN>"

# 5. Gateway conectado
python3 -c "import json;d=json.load(open('/opt/data/gateway_state.json'));print(d['platforms']['whatsapp_cloud']['state'])"
# -> connected
```

**Teste de fogo:** mande uma mensagem real do número de teste→ número atendido.
No log: `inbound message ... chat=<numero>` seguido de `Sending response`.

**Teste sintético** (quando não pode usar o telefone): POST local assinado com
HMAC `X-Hub-Signature-256 = sha256=HMAC_SHA256(app_secret, body)` — útil para
provar que o stack está OK e isolar se o problema é a Meta entregando.

---

## Tabela de troubleshooting

| Sintoma | Causa provável | Fix |
|---|---|---|
| Verify falha no dashboard | tunnel fora / URL errada / verify token | Passo 1-2 do runbook |
| Verify OK mas nada chega | App não inscrito na WABA | `POST /<WABA>/subscribed_apps` |
| POST 200, log limpo, bot mudo | falta `WHATSAPP_CLOUD_ALLOW_ALL_USERS` | set `true` |
| Webhook aponta pra host morto | quick tunnel trocou de URL | named tunnel + URL fixa |
| `flag needs an argument: -token` | var não expandiu no systemd | usar `--token-file` |
| Rota pública não resolve | salvou em Hostname routes (privada) | Published application routes |
| `argotunnel` dá erro de >120 chars | bug do fluxo de login | criar via Zero Trust |
| Cliente recebe "sethome/usage" | patch de notices sem `WHATSAPP_CLOUD` | incluir o enum Cloud |
| Template não envia | fora da janela 24h sem template aprovado | criar template utilidade |

---

## Custos e janela (Meta, 2026)
- Cliente fala primeiro → janela de **24h grátis** pra responder livre-forma.
- Fora da janela → precisa **template aprovado** (utilidade ~R$0,21, marketing
  ~R$0,35). Aprovação leva de horas a dias → planeje com antecedência.
- Para um atendente que só responde (IA 235b livre dentro da janela), o custo
  tende a zero no fluxo comum. Template só para o primeiro toque proativo.
