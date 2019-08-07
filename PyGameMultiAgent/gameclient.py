import pygame
import pygame.locals
import socket
import select
import random
import numpy as np
from baselines.PyGameMultiAgent.staticworld import StaticWorld


class GameClient(object):
    def __init__(self, addr="127.0.0.1", serverport=9009):
        self.clientport = random.randrange(8000, 8999)
        self.conn = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Bind to localhost - set to external ip to connect from other computers
        self.conn.bind(("127.0.0.1", self.clientport))
        self.addr = addr
        self.serverport = serverport

        self.read_list = [self.conn]
        self.write_list = []

        self.setup_pygame()

    def setup_pygame(self):

        self.world = StaticWorld('../Maps/map_1.csv')

        self.screen = pygame.display.set_mode((self.world.local_width * self.world.zoom, self.world.local_length * self.world.zoom))

        pygame.event.set_allowed(None)
        pygame.event.set_allowed([pygame.locals.QUIT,
                                  pygame.locals.KEYDOWN])
        pygame.key.set_repeat(100, 100)                         #move faster


    def run(self):
        running = True
        clock = pygame.time.Clock()
        tickspeed = 30

        try:
            # Initialize connection to server
            self.conn.sendto("cz".encode('utf-8'), (self.addr, self.serverport))
            while running:
                clock.tick(tickspeed)

                # select on specified file descriptors
                readable, writable, exceptional = (
                    select.select(self.read_list, self.write_list, [], 0)
                )
                for f in readable:
                    if f is self.conn:
                        msg, addr = f.recvfrom(2048)
                        msg = msg.decode('utf-8')     #Coordinates of all players

                        self_pos = None
                        AllZombiePose = []

                        for position in msg.split('|')[:-1]:
                            x, y, angle, tag = position.split(',')
                            x = float(x)
                            y = float(y)
                            angle = float(angle)
                            tag = int(tag)
                            if self_pos is None:
                                self_pos = (x, y, angle)
                            AllZombiePose.append((x, y, angle, tag))

                        self.world.draw_local(self.screen, self_pos, AllZombiePose)

                        #self.world.draw_global(self.screen)
                        #self.world.draw_zombie_global(self.screen, (x, y, angle))


                for event in pygame.event.get():
                    if event.type == pygame.QUIT or event.type == pygame.locals.QUIT:
                        running = False
                        break
                    elif event.type == pygame.locals.KEYDOWN:
                        if event.key == pygame.locals.K_UP:
                            self.conn.sendto("uu".encode('utf-8'), (self.addr, self.serverport))
                        elif event.key == pygame.locals.K_LEFT:
                            self.conn.sendto("ul".encode('utf-8'), (self.addr, self.serverport))
                        elif event.key == pygame.locals.K_RIGHT:
                            self.conn.sendto("ur".encode('utf-8'), (self.addr, self.serverport))
                        pygame.event.clear(pygame.locals.KEYDOWN)

                pygame.display.update()
        finally:
            self.conn.sendto("d".encode('utf-8'), (self.addr, self.serverport))


if __name__ == "__main__":
    g = GameClient()
    g.run()