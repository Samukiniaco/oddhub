# PORTS.md — acompanhamento dos ports

Legenda de status: `planejado` | `em andamento` | `protótipo` | `funcional` | `pausado`

## Núcleo
| Item | Status | Notas |
|------|--------|-------|
| core (esqueleto) | em andamento | Contratos e utilitários mínimos; não pronto para produção |
| oddhub (gerenciador) | protótipo | Lista services registrados; UI básica |
| build/release | funcional | tools/build_all.py + GitHub Actions |

## Apps planejados
| App | Tipo | Abordagem | Status | Notas |
|-----|------|-----------|--------|-------|
| WhatsApp | messaging | scraping/web | planejado | Sem API pública de consumidor |
| Instagram | social | scraping/API | planejado | API limitada (Basic Display) |
| Pinterest | social | API oficial | planejado | API disponível |
| Google (busca) | search | Custom Search API | planejado | Requer chave API |
| Google Maps | maps | scraping/geo | planejado | geolocalização via IP/GPS |
| Spotify | music | Web API + previews | planejado | DRM impede stream completo |
| YouTube Music | music | Data API | planejado | Reprodução via mpv quando possível |
| Netflix | streaming | metadados + deep-link | planejado | DRM (Widevine) impede reprodução |
| Crunchyroll | streaming | metadados + deep-link | planejado | DRM impede reprodução |

## Histórico
- (adicione entradas conforme progresso)