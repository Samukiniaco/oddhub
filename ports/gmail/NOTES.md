# Notas — PortMail

## Estado atual

✅ **PortMail concluído com sucesso!**

O port de email foi implementado com:
- Backend demo offline completo (10 emails de exemplo)
- Backend real via IMAP/SMTP (Gmail, Outlook, etc.)
- UI pygame completa com todas as telas
- Teclado virtual navegável por controle
- Persistência em SQLite
- Suporte a handheld (640x480)

## Arquitetura

### Backend Demo (Offline)
- **Fácil de testar**: Sem configuração necessária
- **Funcionalidades completas**: Todas as telas funcionam
- **Zero risco**: Não requer credenciais

### Backend Real (IMAP/SMTP)
- **Gmail**: Requer senha de aplicativo
- **Outlook**: Credenciais normais
- **Outros**: Qualquer provedor IMAP/SMTP

## Melhorias futuras

### Prioridade alta
- [ ] Suporte a anexos (download)
- [ ] Visualização de HTML com imagens inline
- [ ] Suporte a grupos de emails
- [ ] Filtros avançados

### Prioridade média
- [ ] Configuração de contas múltiplas
- [ ] Sincronização automática em background
- [ ] Notificações de novos emails
- [ ] Busca avançada (por remetente, assunto, etc.)

### Prioridade baixa
- [ ] Temas personalizáveis
- [ ] Modo offline com emails baixados
- [ ] Exportação de emails
- [ ] Integração com calendário

## Configuração de contas

### Gmail
1. Ative 2FA na conta Google
2. Gere senha de aplicativo: https://myaccount.google.com/apppasswords
3. Configure no port: Configurações > Contas > Adicionar
4. Use a senha de aplicativo como senha

### Outlook
1. Ative IMAP: https://outlook.live.com/mail/options/general/imapsmtp
2. Configure no port: Configurações > Contas > Adicionar
3. Use credenciais normais

### Outros provedores
- IMAP: imap.provedor.com (porta 993, SSL)
- SMTP: smtp.provedor.com (porta 587, TLS)

## Limites conhecidos

- **Anexos**: Não suportados (download/upload)
- **HTML**: Exibido como texto simples
- **Imagens inline**: Não exibidas
- **Grupos**: Suporte básico
- **Filtros**: Básicos (por pasta, não lidos, etc.)

## Próximos passos

1. **Implementar suporte a anexos** (download de arquivos)
2. **Adicionar visualização HTML** (com imagens inline)
3. **Implementar suporte a grupos** (destinatários múltiplos)
4. **Adicionar filtros avançados** (por remetente, assunto, etc.)

## Notas técnicas

### IMAP/SMTP
- IMAP para recepção (porta 993, SSL)
- SMTP para envio (porta 587, TLS)
- Autenticação com senha de aplicativo (Gmail) ou credenciais normais

### SQLite
- Tabelas: accounts, emails, meta
- Índices: idx_emails_account_folder, idx_emails_ts, idx_emails_thread
- API: get_emails(), upsert_email(), search_emails(), etc.

### UI pygame
- Tela principal: lista de emails
- Detalhe do email: visualização completa
- Compor: envio de novos emails
- Configurações: gerenciamento de contas

## Dados salvos

Emails e configurações ficam em:
- **Windows**: `%APPDATA%\OddHub\PortMail\`
- **Linux**: `~/.local/share/oddhub/gmail/`
- **PortMaster**: `conf/data/` no diretório do port

Arquivos:
- `emails.sqlite3`: Banco de dados SQLite
- `config.json`: Configurações (futuro)
- `PortMail.log`: Logs de execução

## Conclusão

O PortMail está pronto para uso! O modo demo é perfeito para desenvolvimento e testes, enquanto o modo real permite acesso a contas de email reais via IMAP/SMTP.

**Status**: ✅ CONCLUÍDO
**Última atualização**: 2026-11-04
**Autor**: Samuka (baseado no trabalho original)