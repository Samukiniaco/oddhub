# Coletânea de Ports PortMaster — arquitetura modular

## Objetivo
Portar aplicativos "não convencionais" (WhatsApp, Instagram, Pinterest, Google,
Spotify, YouTube Music, Netflix, Crunchyroll, ...) para consoles portáteis via
PortMaster, compartilhando uma base (core) reutilizável.

## Estrutura de pastas
```
<raiz>/
  core/                # biblioteca compartilhada (vendored em cada port no build)
  ports/               # um port por app (release separada)
    _template/         # modelo de port
    cavo/              # (referência) port do jogo CaVo
  tools/               # build, sync, scaffolding
  docs/                # esta documentação
  "port de ref"/       # port de referência original (manter)
```

## Camadas do core
1. **platform/** — abstração de dispositivo: display (pygame), input (teclado/mouse/
   touch/gamepad), settings, storage (conf, bind_directories), saída (quit).
2. **net/** — HTTP (requests com retry), cache em disco com TTL, auth/tokens.
3. **ui/** — renderizador de listas/grids/cards, texto, imagens (download+cache+
   surface), tema.
4. **scrape/** — contrato de serviço (`Service`) e modelo normalizado (`Item`),
   registro de plugins.
5. **media/** — reprodução de mídia via mpv/ffplay (fallback), para vídeo/áudio
   que o pygame não toca (DRM pode impedir — ver riscos).

## Contrato de um serviço (plugin)
```python
class Service:
    id: str            # ex.: "instagram"
    name: str          # nome exibido
    def authenticate(self, creds) -> bool: ...
    def fetch_home(self) -> list[Item]: ...
    def search(self, query) -> list[Item]: ...
    def open(self, item) -> "View": ...   # retorna uma view (tela)
```

## Modelo normalizado
```python
@dataclass
class Item:
    id: str
    title: str
    subtitle: str = ""
    image_url: str = ""
    media_url: str = ""
    kind: str = "card"   # card | list | video | audio | text
    meta: dict = field(default_factory=dict)
```

## Fluxo de um port
1. Launcher `.sh` (modelo CaVo.sh): monta runtime python+pygame, define
   PYTHONPATH com `core/` vendored, roda `main.py`.
2. `main.py`: inicializa platform, carrega o `Service` do app, loop principal
   delega telas para o serviço.
3. Build (`tools/build_release.py`): copia core vendored + app + metadados,
   gera zip.

## Portabilidade para "dispositivos estranhos"
- Toda I/O de dispositivo passa por `platform/` (display, input, storage).
- Novo dispositivo = novo backend em `platform/`, sem tocar nos serviços.
- Entrada já abstrai teclado/mouse/touch/gamepad (referência CaVo).

## Hub (port gerenciador)
- Um port extra `ports/hub` funciona como "gerenciador": lista os apps instalados,
  permite abrir/atualizar/remover e serve de ponto único de entrada.
- Como compartilham o core, o hub pode rodar os serviços in-process (importando
  seus `service.py`) ou lançar o `.sh` de cada port via subprocess.
- O hub também pode baixar novos ports de releases do GitHub.

## Dependências por app
- Cada port declara suas dependências em `requirements.txt` (ex.: requests,
  beautifulsoup4, mpv bindings, pillow, geopy...).
- `tools/fetch_deps.py` (gerado por port) baixa wheels aarch64/cp311 para
  `site-packages/` e `deps/`, seguindo o modelo do port de referência.
- Dependências de sistema (mpv, ffmpeg, libs) vão em `port.json` -> `reqs` e
  são documentadas no README do port.
- O core tenta importar dependências de forma lazy (try/except) para que um app
  não quebre os outros se faltar um pacote.

## GitHub e releases
- Monorepo recomendado: uma pasta por port + core compartilhado.
- GitHub Actions: job por port que roda `tools/sync_core.py <id>` + fetch_deps
  + `tools/build_release.py`, publicando `ports/<id>/*.zip` como release asset.
- Versionamento por port (campo `version` no port.json) e changelog por app.
- O hub pode consultar a API do GitHub para listar releases e baixar zips.

## Gerenciador GUI (port_manager.py)

Para facilitar a manutenção diária, a coletânea inclui um **GUI simples** que
lista os ports (`ports/registry.json`) e permite:

- Selecionar um app e alterar seu **status** (planejado / em andamento / protótipo /
  funcional / pausado).
- **Criar** um novo app (gera o port via `tools/new_port.py` e registra no
  `registry.json`).
- **Excluir** um ou vários apps de uma vez (seleção múltipla com Ctrl/Shift ou
  "Selecionar Tudo"; remove do registro e apaga as pastas dos ports).
- **Reordenar** por prioridade com os botões Subir/Descer.
- Abrir um editor de notas para adicionar/editar observações que são salvas em
  `NOTES.md`.
- Salvar todas as alterações no `registry.json` e `NOTES.md`.

Executar:

```bash
python tools/port_manager.py
```

Como alternativa, `tools/tracker.py` exibe uma lista em modo texto.

## Dispositivos e geolocalização/mídia
- Mídia (vídeo/áudio) via processo externo (mpv/ffplay) em tela cheia, pois
  pygame não decodifica formatos comprimidos/DRM.
- Geolocalização via serviço de IP ou GPS do dispositivo, abstraído em
  `core/platform/geo.py` (a implementar quando necessário).

## Riscos e limitações (importante)
- **DRM/ToS**: Netflix e Crunchyroll não permitem reprodução via scraping
  (Widevine/PlayReady). Só metadados/capas e deep-links. YouTube/Spotify têm
  APIs oficiais com limites. WhatsApp/Instagram não têm API pública de consumidor.
- **Anti-bot**: muitos sites bloqueiam requests simples; pode exigir cookies,
  tokens ou sessões de navegador real.
- **Mídia**: pygame não decodifica vídeo/áudio comprimido; usar mpv/ffplay
  como processo externo (fullscreen) onde o dispositivo permitir.
- **Legalidade**: respeitar ToS e leis locais; preferir APIs oficiais.

## Próximos passos sugeridos
1. Confirmar quais apps entram (pesquisa com amigos).
2. Para cada app: escolher API oficial vs scraping e prototipar o `Service`.
3. Reaproveitar o port de referência (`port de ref`) como primeiro port real
   (já tem pygame + input + display).
4. Criar `tools/new_port.py` para scaffolding.
```

Then core files. Let me write base.py.<|end|><|start|> assistant to=write<|channel|>analysis <|constrain|>xml<|message|><rfl:parameter name="path">
C:\Users\ebinh\Desktop\Coisas do Samuka\Meus Games\Go + SDL PORTS\core\__init__.py