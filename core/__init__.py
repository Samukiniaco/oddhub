"""OddHub core: base compartilhada por todos os ports.

O core nao conhece nenhum app especifico. Ele sabe:

* abrir uma janela 640x480 e escalar para a tela real do aparelho;
* desenhar texto, icones vetoriais, avisos e barras de rolagem;
* mostrar um teclado virtual navegavel pelo controle;
* falar com um backend assincrono (fila de eventos, status);
* achar a pasta de dados do port no XDG e no cartao SD.

Cada port entrega a propria tela, o proprio tema e o proprio backend, e
reutiliza tudo o que esta aqui. Para publicar, copie o core para dentro da
pasta do jogo do port com `python tools/sync_core.py <id>`.
"""

__version__ = "1.0.0"
