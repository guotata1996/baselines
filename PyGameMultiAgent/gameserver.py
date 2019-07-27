import socket
import select
from math import pi as PI
from math import cos, sin, atan2
import numpy as np
from baselines.PyGameMultiAgent.staticworld import StaticWorld
import pygame
import pygame.locals
import time
import sys
import _thread
import sys

# Messages:
#  Client->Server
#   One or two characters. First character is the command:
#     c: connect
#     u: update position
#     d: disconnect
#   Second character only applies to position and specifies direction (udlr)
#
#  Server->Client
#   '|' delimited pairs of positions to draw the players (there is no
#     distinction between the players - not even the client knows where its
#     player is.

# pos: x,y,angle,tag (tag==0: zombie_model, tag==1:bot)

class GameServer(object):
    def __init__(self, port=9009, debug_mode = False):
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Bind to localhost - set to external ip to connect from other computers
        self.listener.bind(("127.0.0.1", port))
        self.read_list = [self.listener]
        self.write_list = []

        self.angle_stepsize = 0.1
        self.players_pose = {}
        self.players_ready = {}
        self.players_reward = {}

        self.world = StaticWorld('../Maps/map_0.csv')

        self.screen = pygame.display.set_mode((self.world.zoom * self.world.length, self.world.zoom * self.world.width)) \
            if sys.platform.startswith('win') else None
        self.debug_mode = debug_mode and sys.platform.startswith('win')


    def do_movement(self, mv, player):

        pos = self.players_pose[player]
        if self.players_pose[player][3] == 0:
            stepsize = 1
        else:
            stepsize = 0.5

        if mv == "u":
            angle = pos[2]
            _x = pos[0] + stepsize * cos(angle)
            _y = pos[1] + stepsize * sin(angle)
            _x = np.clip(_x, 0, self.world.width)
            _y = np.clip(_y, 0, self.world.length)
            new_pos = (_x, _y, angle, pos[3])
            if self.world[new_pos[:2]] == 0:
                self.players_pose[player] = new_pos

        elif mv == "l":
            angle = pos[2] + self.angle_stepsize
            if angle > 2 * PI:
                angle -= 2 * PI
            self.players_pose[player] = (pos[0], pos[1], angle, pos[3])

        elif mv == "r":
            angle = pos[2] - self.angle_stepsize
            if angle < 0:
                angle += 2 * PI
            self.players_pose[player] = (pos[0], pos[1], angle, pos[3])

        else:  # stand idle
            pass

    def init_players_pose(self):
        section_x = [(0, self.world.width // 2), (self.world.width // 2, self.world.width)][np.random.randint(0, 2)]
        section_y = [(0, self.world.length // 2), (self.world.length // 2, self.world.length)][np.random.randint(0, 2)]

        start_position = []

        for p in range(len(self.players_pose)):
            while True:
                new_pose = (np.random.randint(*section_x), np.random.randint(*section_y), np.random.random() * 2 * PI)

                if self.world[(new_pose[0], new_pose[1])] == 1:
                    continue

                noncollision = True
                for existing_pose in start_position:
                    if abs(existing_pose[0] - new_pose[0]) + abs(existing_pose[1] - new_pose[1]) < 8:
                        noncollision = False
                        break

                if noncollision:
                    start_position.append(new_pose)
                    break

        for k in zip(self.players_pose.keys(), start_position):
            self.players_pose[k[0]] = *(k[1]), self.players_pose[k[0]][3]

    def _send_to_client(self):
        for player in list(self.players_pose):
            send = []
            for pos in list(self.players_pose):
                if player == pos:
                    send.insert(0, "{0},{1},{2},{3}".format(*self.players_pose[pos]))
                else:
                    send.append("{0},{1},{2},{3}".format(*self.players_pose[pos]))
            self.listener.sendto('|'.join(send).encode('utf-8'), player)

    def run(self):
        last_updated_time = time.time()
        clock = pygame.time.Clock()
        try:
            while True:

                if self.screen is not None:
                    if self.debug_mode:
                        clock.tick(0.5)
                        self.world.draw_global(self.screen, self.players_pose, self.players_reward)
                        pygame.display.update()

                    elif time.time() - last_updated_time > 0.03:
                        self.world.draw_global(self.screen, self.players_pose, self.players_reward)
                        pygame.display.update()
                        last_updated_time = time.time()

                    for event in pygame.event.get():
                        if event.type == pygame.QUIT or event.type == pygame.locals.QUIT:
                            pygame.quit()

                    pygame.display.update()

                readable, writable, exceptional = (
                    select.select(self.read_list, self.write_list, [])
                )
                for f in readable:
                    if f is self.listener:
                        msg, addr = f.recvfrom(2048)
                        msg = msg.decode('utf-8')
                        if len(msg) >= 1:
                            cmd = msg[0]
                            if cmd == "c":  # New Connection
                                if msg[1] == "z": # New Connection from zombie (model)
                                    self.players_pose[addr] = (0, 0, 0, 0)
                                else:
                                    self.players_pose[addr] = (0, 0, 0, 1)

                                self.players_ready[addr] = True
                                self.init_players_pose()
                            elif cmd == "u":  # Movement Update
                                if len(msg) >= 2 and addr in self.players_pose:
                                    # Second char of message is direction (udlr)
                                    self.do_movement(msg[1], addr)
                                    self.players_ready[addr] = True
                                    if len(msg) > 2:
                                        self.players_reward[addr] = float(msg[2:])

                            elif cmd == "d":  # Player Quitting
                                if addr in self.players_pose:
                                    del self.players_pose[addr]
                                    del self.players_ready[addr]
                            elif cmd == "r":
                                self.players_ready[addr] = True
                                self.init_players_pose()
                            else:
                                print ("Unexpected: {0}".format(msg))

                            allready = all(elem for elem in self.players_ready.values())
                            if allready:
                                self._send_to_client()


        except KeyboardInterrupt as e:
            pass


if __name__ == "__main__":
    g = GameServer()
    g.run()