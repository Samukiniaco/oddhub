# core — base compartilhada (EM DESENVOLVIMENTO)

> **Aviso:** este núcleo é um esqueleto/template. As dependências, os
> contratos e os módulos aqui presentes **não estão prontos para uso em
> produção**. Servem de base para os ports que serão implementados.

- `scrape/`: contratos (`Item`, `Service`) e registro de plugins — estáveis
  o suficiente para começar, mas podem mudar.
- `net/`, `platform/`, `ui/`, `media/`: utilitários mínimos, a completar
  conforme cada app exigir.
- Nenhum app (port) está funcional ainda; veja `PORTS.md` para o status.