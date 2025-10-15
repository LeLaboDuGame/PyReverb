import socket
import threading
import time
import random
import pygame
from pygame import Vector2, Surface

from reverb import *

ReverbManager.REVERB_SIDE = [ReverbSide.SERVER, ReverbSide.CLIENT][int(input("1-SERVER\n2-CLIENT\n>>> ")) - 1]

"""@ReverbManager.reverb_object_attribute
class Bullet(ReverbObject):
    def __init__(self, pos, dir, color, belonging_membership:int=None):
        self.color = color
        self.dir = dir
        self.pos = pos
        self.speed = 2
        super().__init__(pos, dir, color, belonging_membership=belonging_membership)

    def on_init_from_client(self):
        threading.Thread(target=self.update).start()
        self.compute_server(self.die_after_time, 2)

    def update(self):
        while is_running:
            self.pos += Vector2(self.dir) * self.speed
            clock.tick(tick)

    # SERVER SIDE
    def die_after_time(self, t):
        time.sleep(t)
        ReverbManager.remove_reverb_object(self.uid)"""


@ReverbManager.reverb_object_attribute
class Player(ReverbObject):
    def __init__(self, pos=[0, 0], dir=[0, 0], color="red", uid="Unknow", add_on_init=True, belonging_membership:int=None):
        self.pos = pos
        self.dir = dir
        self.color = color
        super().__init__(pos, dir, color, uid=uid, add_on_init=add_on_init, belonging_membership=belonging_membership)


    def on_init_from_client(self):
        threading.Thread(target=self.play).start()

    @staticmethod
    def choose_rnd_color():
        return ["green", "red", "blue1", "yellow"][random.randint(0, 3)]

    def play(self):
        while is_running:
            if self.is_owner():
                while is_running:
                    keys = pygame.key.get_pressed()
                    dir = ""
                    if keys[pygame.K_z]:
                        dir += "Z"
                    if keys[pygame.K_s]:
                        dir += "S"
                    if keys[pygame.K_q]:
                        dir += "Q"
                    if keys[pygame.K_d]:
                        dir += "D"
                    if dir != "":
                        self.compute_server(self.check_walk, dir)

                    if keys[pygame.K_SPACE]:
                        self.compute_server(self.spawn_bullet)


                    clock.tick(tick)
    # ON SERVER
    def check_walk(self, dir):
        self.dir = [0, 0]
        for d in dir:
            def is_pos_in_map_bound(pos: Vector2):
                return 0 <= pos.x <= map_size[0] and 0 <= pos.y <= map_size[1]
            speed = 5
            l_pos = {"Z": (0, -1), "S": (0, 1), "D": (1, 0), "Q": (-1, 0)}
            self.dir = list(self.dir + Vector2(l_pos[d]))

        print(self.dir)
        new_pos = self.pos + Vector2(self.dir) * speed
        if is_pos_in_map_bound(new_pos):
            self.pos = list(new_pos)

    def spawn_bullet(self):
        """Bullet(self.pos, self.dir, self.color, belonging_membership=self.belonging_membership)"""

@server_event_registry.on_event("client_connection")
def on_connecting(clt:socket.socket, *args):
    print("OK")
    Player(pos=[400, 400], color=Player.choose_rnd_color(), belonging_membership=clt.getpeername()[1])

@server_event_registry.on_event("client_disconnection")
def on_disconnecting(clt:socket.socket, *args):
    for p in ReverbManager.get_all_ro_by_type(Player):
        if p.belonging_membership == clt.getpeername()[1]:
            ReverbManager.remove_reverb_object(p.uid)


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

        screen.fill("purple")

        for p in ReverbManager.get_all_ro_by_type(Player):
            print(p.pos)
            pygame.draw.circle(screen, p.color, p.pos, 3)

        """for b in ReverbManager.get_all_ro_by_type(Bullet):
            pygame.draw.line(screen, b.color, b.pos - b.dir, b.pos + b.dir)"""


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
        try:
            time.sleep(1/tick)
            ReverbManager.server_sync()
        except KeyboardInterrupt:
            serv.stop_server()

