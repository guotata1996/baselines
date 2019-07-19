import socket
import select
from math import pi as PI
from math import cos, sin, atan2
import numpy as np
from baselines.PyGameMultiAgent.staticworld import StaticWorld
import pygame
import pygame.locals
import _thread

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
    def __init__(self, port=9009, visualize_global = False):
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Bind to localhost - set to external ip to connect from other computers
        self.listener.bind(("127.0.0.1", port))
        self.read_list = [self.listener]
        self.write_list = []

        self.angle_stepsize = 0.1
        self.players = {}
        self.world = StaticWorld('../Maps/map_0.csv')
        self.starting_pos = self.calc_players_position()

        self.visualize = visualize_global

    def do_movement(self, mv, player):

        pos = self.players[player]
        if self.players[player][3] == 0:
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
                self.players[player] = new_pos

        elif mv == "l":
            angle = pos[2] + self.angle_stepsize
            if angle > 2 * PI:
                angle -= 2 * PI
            self.players[player] = (pos[0], pos[1], angle, pos[3])

        elif mv == "r":
            angle = pos[2] - self.angle_stepsize
            if angle < 0:
                angle += 2 * PI
            self.players[player] = (pos[0], pos[1], angle, pos[3])

        else:  # stand idle
            pass

    def calc_players_position(self, cnt = 16):
        start_position = []

        for p in range(cnt):
            while True:
                new_pose = (np.random.randint(0, self.world.width // 2), np.random.randint(0, self.world.length // 2), np.random.randint(0, 359))

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
        return start_position

    def init_players_pose(self):
        np.random.shuffle(self.starting_pos)
        for k in zip(self.players.keys(), self.starting_pos):
            self.players[k[0]] = *(k[1]), self.players[k[0]][3]

    def _send_to_client(self):
        clock = pygame.time.Clock()
        while True:
            clock.tick(24)
            for player in list(self.players):
                send = []
                for pos in list(self.players):
                    if player == pos:
                        send.insert(0, "{0},{1},{2},{3}".format(*self.players[pos]))
                    else:
                        send.append("{0},{1},{2},{3}".format(*self.players[pos]))
                self.listener.sendto('|'.join(send).encode('utf-8'), player)

    def _visualize_global(self):
        clock = pygame.time.Clock()
        screen = pygame.display.set_mode((self.world.zoom * self.world.length, self.world.zoom * self.world.width))
        running = True
        while running:
            clock.tick(30)
            self.world.draw_global(screen, self.players.values())

            for event in pygame.event.get():
                if event.type == pygame.QUIT or event.type == pygame.locals.QUIT:
                    pygame.quit()
            pygame.display.update()

    def run(self):
        print("Waiting...")
        _thread.start_new_thread(self._send_to_client, ())
        if self.visualize:
            _thread.start_new_thread(self._visualize_global, ())

        try:
            while True:

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
                                    self.players[addr] = (0, 0, 0, 0)
                                else:
                                    self.players[addr] = (0, 0, 0, 1)
                                self.init_players_pose()
                            elif cmd == "u":  # Movement Update
                                if len(msg) >= 2 and addr in self.players:
                                    # Second char of message is direction (udlr)
                                    self.do_movement(msg[1], addr)
                            elif cmd == "d":  # Player Quitting
                                if addr in self.players:
                                    del self.players[addr]
                            else:
                                print ("Unexpected: {0}".format(msg))


        except KeyboardInterrupt as e:
            pass


if __name__ == "__main__":
    g = GameServer()
    g.run()