# Template de port

Modelo usado por `tools/new_port.py`. Nao e um port: e o esqueleto que vira um
port novo.

```
_template/
  port.json          # metadados do PortMaster (schema v4), com marcadores
  gameinfo.xml       # metadados para a interface do CFW
  README.md          # notas + controles
  testing_thread.txt # texto do thread de teste
  template.sh        # launcher (vira <Titulo>.sh)
  template/          # conteudo da pasta do jogo
    template.ini     # mapa de controles do gptokeyb2 (vira <id>.ini)
    fetch_deps.py    # gera site-packages/ no PC
    licenses/
    template/        # pacote python (vira <pacote>/)
```

Marcadores substituidos na geracao: `{{ID}}`, `{{ID_UPPER}}`, `{{TITLE}}`,
`{{SCRIPT}}`, `{{PACKAGE}}`, `{{CLASS}}`, `{{GENRE}}`, `{{GENRE_TITLE}}`,
`{{DESC}}`, `{{DATE}}`, `{{URL}}`.

Depois de gerar um port, rode `python tools/sync_core.py <id>` para copiar o
core para dentro da pasta do jogo.