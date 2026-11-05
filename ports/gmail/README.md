# PortMail - Port de Email para PortMaster

## Visão geral

O PortMail é um port de email para o PortMaster que permite ler, compor e gerenciar emails diretamente no dispositivo. Suporta o modo demo (offline) e o backend real (IMAP/SMTP).

## Funcionalidades

### Modo Demo (Offline)
- **Conversas de exemplo**: 10 emails de exemplo para teste e demonstração
- **Envio simulado**: Componha e envie emails (armazenados localmente)
- **Interface completa**: Todas as telas funcionam sem conexão
- **Zero risco**: Não requer configuração ou credenciais

### Modo Real (IMAP/SMTP)
- **Contas reais**: Conecte-se a qualquer conta IMAP/SMTP (Gmail, Outlook, etc.)
- **Sincronização**: Baixe emails do servidor
- **Envio real**: Envie emails através do servidor SMTP
- **Busca**: Pesquise em todos os emails baixados

## Como usar

### Iniciar em modo demo (padrão)
```bash
cd ports/gmail
python gmail/main.py
```

### Iniciar em modo real
```bash
cd ports/gmail
python gmail/main.py --backend imap
```

### Launcher do PortMaster
```bash
cd ports/gmail
./PortMail.sh
```

### Testes
```bash
# Self-test (sem UI)
python gmail/main.py --selftest

# Smoke test da UI
python portmail_smoke.py
```

## Configuração do backend real

### Gmail
1. Ative autenticação em duas etapas na conta Google
2. Gere uma senha de aplicativo: https://myaccount.google.com/apppasswords
3. Configure no port: Configurações > Contas > Adicionar
4. Use a senha de aplicativo como senha

### Outlook/Hotmail
1. Ative IMAP no Outlook: https://outlook.live.com/mail/options/general/imapsmtp
2. Configure no port: Configurações > Contas > Adicionar
3. Use suas credenciais normais

### Outros provedores
- Configure IMAP: imap.provedor.com (porta 993, SSL)
- Configure SMTP: smtp.provedor.com (porta 587, TLS)

## Estrutura

```
ports/gmail/
├── PortMail.sh              # Launcher do PortMaster
├── gmail/                   # Diretório principal do app
│   ├── __init__.py
│   ├── __main__.py
│   ├── config.py           # Configuração e tema visual
│   ├── models.py           # Modelos de dados (Email, Account, etc.)
│   ├── store.py            # Persistência SQLite
│   ├── main.py             # Entry point
│   ├── backend/            # Backends de email
│   │   ├── __init__.py
│   │   ├── base.py         # Contrato de backend
│   │   ├── demo.py         # Backend offline (demo)
│   │   └── imap_backend.py # Backend real (IMAP/SMTP)
│   └── ui/                 # Camada visual (pygame)
│       ├── __init__.py
│       ├── app.py          # Tela principal
│       ├── widgets.py      # Componentes de UI
│       └── keyboard.py     # Teclado virtual
├── requirements.txt
├── README.md
└── NOTES.md
```

## Navegação

### Teclado
- **↑ ↓**: Navegar na lista de emails
- **Enter**: Abrir email selecionado
- **Esc**: Voltar
- **F1**: Ajuda

### Mouse
- **Clicar em email**: Abrir
- **Scroll**: Navegar
- **Botões no header**: Configurações, busca, sincronizar

### Gamepad
- **A**: Confirmar/Abrir
- **B**: Voltar
- **X**: Compor novo email
- **Y**: Pesquisar
- **Start**: Configurações

## Limites

- **Anexos**: Não suportados nesta versão
- **HTML**: Emails HTML são exibidos como texto simples
- **Imagens**: Imagens inline não são exibidas
- **Grupos**: Suporte básico a grupos de emails

## Dados

Emails e configurações são salvos em:
- **Windows**: `%APPDATA%\OddHub\PortMail\`
- **Linux**: `~/.local/share/oddhub/gmail/`
- **PortMaster**: `conf/data/` no diretório do port

## Suporte

Para problemas ou sugestões:
1. Verifique o log em `conf/log.txt` (PortMaster) ou `PortMail.log` (desktop)
2. Teste em modo demo primeiro para isolar problemas
3. Verifique as configurações da conta IMAP/SMTP

## Licença

Port do OddHub. Veja LICENSE.md para detalhes.