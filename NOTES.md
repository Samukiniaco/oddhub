# Notas de pesquisa — OddHub

Use `python tools/note.py "texto"` para adicionar rapidamente.
Ou edite este arquivo diretamente.

---
- [2026-11-04 19:57] É um port complicado devido a possibilidade de ban por Scraping, ou seja, precisa ser feito de forma fechada para proteger a conta disso e ainda conseguir usar o WhatsApp, obviamente, o objetivo desses ports é ser otimizado e leve, então não iremos usar Tauri nem nada para rodar coisas como WhatsApp Web para usar APIs de Scraping prontas como WA-js, mas isso não nos impede de estudá-las para entender como funcionam e aplicar, embora para WhatsApp Web sirvam mais para mostrar de forma diferente, então teremos que analisar bem como isso vai funcionar. Eu tenho uma sugestão para caso nada funcione para rodar diretamente o WhatsApp, que é:
- [2026-11-04 19:57] Um script pode rodar de forma autônoma no meu celular ou PC, que captura todas as mensagens e tal com um scraping pra entender o conteúdo de diferentes tipos, o PC manda esses dados para o Port exibir, o problema é que perde um pouco da graça do port em si.
- [2026-11-04 19:57] (Obs: diferente dos outros ports que contém um nome diferente do id, esse é um port que irá tentar seguir exatamente como o WhatsApp de fato, porém, os outros, servem como alternativas que funcionam de forma semelhante ou igual, com exceção do Youtube, no qual o yt-dlp de fato captura seus vídeos, irei marcar com "*" os ports que seguirão como o WhatsApp para fácil entendimento)