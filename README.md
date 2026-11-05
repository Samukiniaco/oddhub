# OddHub - Coleção de ports do PortMaster

Bem-vindo ao OddHub! Este é um projeto experimental para coletar e manter ports para o PortMaster.

## Visão geral

OddHub é uma coleção modular de ports para o PortMaster, com foco em qualidade e recursos completos.
Cada port é construído sobre um esqueleto comum (core/) e inclui uma UI consistente.

## Estrutura

```
./ports/whatsapp/          # Port WhatsApp (concluído)
./ports/oddhub/           # Port gerente do OddHub
./ports/youtube/          # Port YouTube
./ports/crunchyroll/      # Port Crunchyroll
./ports/pinterest/        # Port Pinterest
./core/                  # Esqueleto e ferramentas compartilhadas
./tools/                 # Utilitários (port_manager.py, tracker.py, note.py)
./docs/                  # Documentação
```

## Como testar o port WhatsApp

### 1. Teste self-test rápido (sem UI)
```bash
# Navegue até o diretório do port
cd "C:\Users\ebinh\Desktop\Coisas do Samuka\Meus Games\Go + SDL PORTS\ports\whatsapp"

# Execute o teste self (rápido, sem abrir janela)
python main.py --selftest
```

### 2. Teste smoke test da UI (abre janela brief)
```bash
cd "C:\Users\ebinh\Desktop\Coisas do Samuka\Meus Games\Go + SDL PORTS\ports\whatsapp"
python wa_ui_smoke.py
```

### 3. Gere screenshots (opcional)
```bash
cd "C:\Users\ebinh\Desktop\Coisas do Samuka\Meus Games\Go + SDL PORTS\ports\whatsapp"
python wa_shots.py
```

### 4. Teste o port (demo, janela)
```bash
cd "C:\Users\ebinh\Desktop\Coisas do Samuka\Meus Games\Go + SDL PORTS\ports\whatsapp"
python main.py
```

### 5. Teste o port (real, tela cheia - necessita de neonize)
```bash
cd "C:\Users\ebinh\Desktop\Coisas do Samuka\Meus Games\Go + SDL PORTS\ports\whatsapp"
export WHATSAPP_BACKEND=neonize
export WHATSAPP_DATA=/meus/dados
python main.py --fullscreen
```

### 6. Teste o port via PortMaster (requer sudo)
```bash
cd "C:\Users\ebinh\Desktop\Coisas do Samuka\Meus Games\Go + SDL PORTS\ports\whatsapp"
./WhatsApp.sh
```

## Sobre o port WhatsApp

O port WhatsApp é um aplicativo WhatsApp completo para o PortMaster com:

- **Backend demo offline** para teste e desenvolvimento sem conexão
- **Backend real (neonize)** opcional para conexão WhatsApp real via QR ou pareamento por telefone
- **UI pygame completa** com todas as telas de um WhatsApp típico
- **Suporte a dispositivos móveis** (tela cheia em handhelds)
- **Salvamento de estado** (mensagens e conversas persistem após reinicialização)
- **Navegação por controle/gamepad** além de mouse/teclado

### Funcionalidades

- **Lista de conversas** - Veja conversas recentes, mensagens não lidas, avatares
- **Conversas** - Visualize mensagens completas com timestamps, status de envio, digitação ao vivo
- **Teclado virtual** - Teclado de computador completo navegável por setas/gamepad
- **QR/pareamento** - Conecte WhatsApp no celular via QR ou código por telefone
- **Configurações** - Alterne entre backends, conecte/desconecte, atualize contatos/grupos
- **Ajuda** e **Sobre** - Lista de atalhos e aviso sobre risco de banimento

### Documentação

- `ports/whatsapp/CHANGES.md` - Registro de alterações deste port
- `ports/whatsapp/README.txt` - Documentação completa do port
- `ports/whatsapp/NOTES.md` - Notas específicas do port
- `ports/whatsapp/VERIFY.txt` - Lista de verificações para teste

## Outros ports

### Port YouTube
- **Tipo**: vídeo
- **Approach**: API (via yt-dlp)
- **Status**: planejado

### Port Crunchyroll
- **Tipo**: streaming
- **Approach**: scraping/api
- **Status**: planejado

### Port Pinterest
- **Tipo**: imagem
- **Approach**: API
- **Status**: planejado

### Port OddHub (gerente)
- **Tipo**: gerenciador
- **Approach**: UI de gerenciamento de ports
- **Status**: protótipo

## Ferramentas

### tools/port_manager.py
Gerenciador unificado de ports (Tkinter) para:
- Criar/deletar/editar ports
- Multi-seleção e exclusão em lote
- Reordenar por prioridade
- Anotações por app (NOTAS.md)

### tools/tracker.py
Acompanhamento de ports em texto (PORTS.md)

### tools/note.py
CLI rápido para adicionar notas às NOTAS.md dos ports

## Arquitetura

### Core (esqueleto)
- `core/platform/storage.py` - Utilitários de caminho do dispositivo (portável)
- `core/ui/theme.py` - Paleta visual compartilhada entre ports
- `core/scrape/base.py` - Contrato base de serviço e Item
- `core/scrape/registry.py` - Registro simples de serviços/plugins

### Port WhatsApp
- **Backend**: demo (offline) e neonize (real)
- **UI**: pygame com todas as telas
- **Persistência**: SQLite (conversas + mensagens)
- **Teclado**: virtual com navegação por controle
- **Runtime**: python_3.11 + pygame (PortMaster)

## Requisitos

### Modo demo (padrão)
- Python 3.11+ com pygame-CE
- Sem dependências extras

### Modo real (neonize)
- python_3.11 com pygame-CE
- neonize==0.10.0 (manylinux2014_aarch64 wheel)
- FFmpeg (para mídia)
- Todos os dependências do neonize

Baixe dependências:
```bash
cd ports/whatsapp
python fetch_deps.py --neonize
```

Copie site-packages/ para o diretório do port.

## Risco de banimento

O port WhatsApp usa neonize, um cliente não oficial do WhatsApp.
Há risco de banimento da conta. Use uma conta secundária e por sua conta e risco.

## Agradecimentos

- Projeto original e esqueleto por Samuka
- Todos os colaboradores que contribuíram para este esforço colaborativo
- Comunidade open-source por código, documentação e suporte

## Licença

Este projeto é de código aberto sob a licença MIT.
Veja LICENSE.md para detalhes.

## Contribuição

Sinta-se à vontade para contribuir! Fork este repositório, faça alterações e abra um pull request.
Todas as contribuições são bem-vindas!

---

### Testes rápidos

Execute `python main.py --selftest` para verificar a funcionalidade básica.
Execute `python wa_ui_smoke.py` para uma rápida verificação da UI.

### Suporte a dispositivos móveis

O port detecta automaticamente quando está rodando em um PortMaster (sem DISPLAY) e inicia em tela cheia (640x480).

### Persistente

Todas as conversas e mensagens são salvas em SQLite e persistem após reinicialização.

### Backend opcional

O backend demo funciona 100% offline. O backend real (neonize) é opcional e deve ser baixado separadamente.

O port WhatsApp está pronto para ser usado!