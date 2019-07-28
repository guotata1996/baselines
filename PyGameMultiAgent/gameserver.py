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
    map_count = 1

    def __init__(self, port=9009, visualize = True):
        print(time.asctime(time.localtime(time.time())))

        self.listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Bind to localhost - set to external ip to connect from other computers
        self.listener.bind(("127.0.0.1", port))
        self.read_list = [self.listener]
        self.write_list = []

        self.players_pose = {}
        self.players_ready = {}
        self.players_reward = {}

        self.map_index = 0
        self.world = StaticWorld('../Maps/map_0.csv')

        self.screen = pygame.display.set_mode((self.world.zoom * self.world.length, self.world.zoom * self.world.width)) \
            if sys.platform.startswith('win') and visualize else None

    # mv is in format [l/r/u][(optional)float]
    def do_movement(self, move, player):
        pos = self.players_pose[player]
        mv = move[0]

        if len(move) > 1:
            stepsize = float(move[1:])
        else:
            if self.players_pose[player][3] == 0:
                if mv == "u":
                    stepsize = 1
                else:
                    stepsize = 0.5
            else:
                if mv == "u":
                    stepsize = 2
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
            angle = pos[2] + stepsize
            if angle > 2 * PI:
                angle -= 2 * PI
            self.players_pose[player] = (pos[0], pos[1], angle, pos[3])

        elif mv == "r":
            angle = pos[2] - stepsize
            if angle < 0:
                angle += 2 * PI
            self.players_pose[player] = (pos[0], pos[1], angle, pos[3])

        else:  # stand idle
            pass

    def init_players_pose(self):
        while True:
            self.map_index = np.random.randint(0, self.map_count)
            del self.world
            self.world = StaticWorld("../Maps/map_{0}.csv".format(self.map_index))
            section_x = [(0, self.world.width // 2), (self.world.width // 2, self.world.width)][np.random.randint(0, 2)]
            section_y = [(0, self.world.length // 2), (self.world.length // 2, self.world.length)][np.random.randint(0, 2)]

            start_position = []

            for p in range(len(self.players_pose)):
                trial_cnt = 0
                while trial_cnt < 5:
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

                    trial_cnt += 1

                # If cannot find a suitable location for a new player, move to new map
                if trial_cnt == 5:
                    break

            # If all playerStarts are ready, break from main loop
            if len(start_position) == len(self.players_pose):
                for k in zip(self.players_pose.keys(), start_position):
                    self.players_pose[k[0]] = *(k[1]), self.players_pose[k[0]][3]
                break

    def _send_to_client(self, addr = None):
        if addr is not None:
            send = []
            for pos in list(self.players_pose):
                if pos == addr:
                    send.insert(0, "{0},{1},{2},{3}".format(*self.players_pose[pos]))
                else:
                    send.append("{0},{1},{2},{3}".format(*self.players_pose[pos]))

            send.append(str(self.map_index))
            self.listener.sendto('|'.join(send).encode('utf-8'), addr)
        else:
            for player in list(self.players_pose):
                send = []
                for pos in list(self.players_pose):
                    if player == pos:
                        send.insert(0, "{0},{1},{2},{3}".format(*self.players_pose[pos]))
                    else:
                        send.append("{0},{1},{2},{3}".format(*self.players_pose[pos]))
                send.append(str(self.map_index))
                self.listener.sendto('|'.join(send).encode('utf-8'), player)

    def run(self):
        last_updated_time = time.time()
        try:
            while True:

                if self.screen is not None:
                    if time.time() - last_updated_time > 0.03:
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
                            elif cmd == "u":
                                # Movement Update  ul0.3|0.5
                                # left 0.3, reward 0.5
                                if len(msg) >= 2 and addr in self.players_pose:
                                    if "|" in msg:
                                        msg_mv, msg_rew = msg[1:].split('|')
                                    else:
                                        msg_mv = msg[1:]
                                        msg_rew = None

                                    self.do_movement(msg_mv, addr)
                                    self.players_ready[addr] = True
                                    if msg_rew is not None:
                                        self.players_reward[addr] = float(msg_rew)

                            elif cmd == "d":  # Player Quitting
                                if addr in self.players_pose:
                                    del self.players_pose[addr]
                                    del self.players_ready[addr]
                            elif cmd == "r":
                                self.init_players_pose()
                                self._send_to_client(addr)
                            else:
                                print ("Unexpected: {0}".format(msg))

                            allready = all(elem for elem in self.players_ready.values())
                            if allready:
                                self._send_to_client()
                                self.players_ready = dict.fromkeys(self.players_ready, False)


        except KeyboardInterrupt as e:
            pass


if __name__ == "__main__":
    g = GameServer()
    g.run()