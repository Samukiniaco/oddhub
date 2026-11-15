# Notas de pesquisa — OddHub

Use `python tools/note.py "texto"` para adicionar rapidamente.
Ou edite este arquivo diretamente.

---
- [2026-11-15] Port Gmail reescrito do zero seguindo o `portmaster-ai-complete-reference.md`. Decisoes: layout de PR (Gmail.sh + pasta `gmail/` com metadados ao lado, igual ao `port de ref`), `port.json` no schema v4, runtime `python_3.11`, controles via `gmail.ini` do gptokeyb2 (o app nao abre a API de joystick, para nao duplicar entrada), desenho sempre em 640x480 escalado para a tela real, campos de texto lendo `pygame.TEXTINPUT` e um teclado virtual proprio para quem nao tem teclado fisico. Conta real por IMAP/SMTP da stdlib (senha de aplicativo do jogador), modo demo offline sem credencial. `port de ref` saiu do git: e referencia tecnica e nao vai para o GitHub.
