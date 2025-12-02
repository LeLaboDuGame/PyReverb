import pygame
from pygame import Vector2, Surface

from pyreverb import reverb
from pyreverb.Exemple.shooter_objects import Player, Bullet, MAP_SIZE, TICK
from pyreverb.reverb import *

clock = pygame.time.Clock()
reverb.VERBOSE = 2  # make it speak less


def start_client(is_host=False, port=8080, admin_key: int = 1000):
    pygame.init()
    screen: Surface = pygame.display.set_mode(MAP_SIZE)
    is_running = True
    print("Pygame is init !")

    ReverbManager.IS_HOST = is_host
    ReverbManager.REVERB_SIDE = ReverbSide.CLIENT
    clt = Client(port=port)
    ReverbManager.REVERB_CONNECTION = clt
    clt.connect()
    ReverbManager.log_as_admin(admin_key)

    while is_running and ReverbManager.REVERB_CONNECTION.is_connected:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                is_running = False

        screen.fill("purple")

        for p in ReverbManager.get_all_ro_by_type(Player):
            pygame.draw.circle(screen, p.color.get(), tuple(p.pos.get()), 3)

        for b in ReverbManager.get_all_ro_by_type(Bullet):
            pygame.draw.line(screen, b.color.get(), Vector2(b.pos.get()) - Vector2(b.dir.get()),
                             Vector2(b.pos.get()) + Vector2(b.dir.get()), 1)

        pygame.display.flip()
        clock.tick(TICK)

    print("Closing the game...")
    pygame.quit()
    if ReverbManager.IS_HOST:
        ReverbManager.stop_server_admin()
    else:
        clt.disconnect()
    # Stop distant server



if __name__ == "__main__":
    print("Starting client from main!")
    start_client()
