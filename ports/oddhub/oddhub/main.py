"""Hub gerenciador - entry point."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # ports/hub
if os.path.isdir(os.path.join(HERE, "core")):
    sys.path.insert(0, HERE)
elif os.path.isdir(os.path.join(ROOT, "core")):
    sys.path.insert(0, ROOT)

try:
    import pygame
except Exception:
    pygame = None

from core.scrape.registry import registry

# Carrega services locais, se existirem
services_dir = os.path.join(HERE, "services")
if os.path.isdir(services_dir):
    sys.path.insert(0, os.path.dirname(services_dir))
    try:
        import services  # noqa
    except Exception as e:
        print("hub: falha ao carregar services:", e)


def main():
    print("Hub - servicos registrados:", registry.ids())
    if pygame is None:
        print("pygame indisponivel; modo texto.")
        for sid in registry.ids():
            print(" -", sid)
        return
    pygame.init()
    screen = pygame.display.set_mode((640, 480))
    pygame.display.set_caption("OddHub")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 28)
    running = True
    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                running = False
        screen.fill((16, 18, 30))
        y = 20
        title = font.render("Hub - apps", True, (235, 240, 250))
        screen.blit(title, (20, y)); y += 40
        for sid in registry.ids():
            txt = font.render("- " + sid, True, (64, 224, 255))
            screen.blit(txt, (40, y)); y += 30
        if not registry.ids():
            msg = font.render("(nenhum service registrado)", True, (120, 130, 160))
            screen.blit(msg, (40, y))
        pygame.display.flip()
        clock.tick(30)
    pygame.quit()


if __name__ == "__main__":
    main()