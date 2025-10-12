import time
import random
import pygame
from pygame import Vector2, Surface

from reverb import *

ReverbManager.REVERB_SIDE = [ReverbSide.SERVER, ReverbSide.CLIENT][int(input("1-SERVER\n2-CLIENT\n>>> ")) - 1]

if ReverbManager.REVERB_SIDE == ReverbSide.CLIENT:
    pass

@ReverbManager.reverb_object_attribute
class Player(ReverbObject):
    def __init__(self, pos=[0, 0], dir="Z", color="red", uid=None, add_on_init=True, belonging_membership:int=None):
        self.pos = pos
        self.dir = dir
        self.color = color
        super().__init__(pos, dir, color, uid=uid, add_on_init=add_on_init, belonging_membership=belonging_membership)


    def on_init_from_client(self):
        threading.Thread(target=self.play).start()

    @staticmethod
    def choose_rnd_color():
        return ["green", "red", "purple", "yellow"][random.randint(0, 3)]

    def play(self):
        while is_running:
            if self.is_owner():
                while is_running:
                    keys = pygame.key.get_pressed()
                    if keys[pygame.K_z]:
                        self.compute_server(self.check_walk, "Z")
                    elif keys[pygame.K_s]:
                        self.compute_server(self.check_walk, "S")
                    elif keys[pygame.K_q]:
                        self.compute_server(self.check_walk, "Q")
                    elif keys[pygame.K_d]:
                        self.compute_server(self.check_walk, "D")
                    clock.tick(tick)
    # ON SERVER
    def check_walk(self, dir):
        def is_pos_in_map_bound(pos: Vector2):
            return 0 <= pos.x <= map_size[0] and 0 <= pos.y <= map_size[1]
        speed = 5
        l_pos = {"Z": (0, -1), "S": (0, 1), "D": (1, 0), "Q": (-1, 0)}
        new_pos = self.pos + Vector2(l_pos[dir]) * speed
        if is_pos_in_map_bound(new_pos):
            self.pos = list(new_pos)

@server_event_registry.on_event("client_connection")
def on_connecting(clt:socket.socket, *args):
    Player(pos=[400, 400], color=Player.choose_rnd_color(), belonging_membership=clt.getpeername()[1])


map_size = (800, 800)
tick = 60

if ReverbManager.REVERB_SIDE == ReverbSide.CLIENT:

    pygame.init()
    screen: Surface = pygame.display.set_mode(map_size)
    clock = pygame.time.Clock()
    is_running = True
    print("Pygame is init !")

    clt = Client()
    ReverbManager.REVERB_CONNECTION = clt
    clt.connect()


    while is_running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                is_running = False

        screen.fill("white")
        for p in ReverbManager.get_all_ro_by_type(Player):
            pygame.draw.circle(screen, p.color, p.pos, 3)

        pygame.display.flip()
        clock.tick(tick)

    print("Closing the game...")
    pygame.quit()
    clt.disconnect()

else:
    serv = Server()
    ReverbManager.REVERB_CONNECTION = serv
    serv.start_server()
    while True:
        time.sleep(1/tick)
        ReverbManager.server_sync()
