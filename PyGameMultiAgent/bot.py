import random
import socket
import pygame
import signal
import select
from math import atan2, degrees, radians
import sys
from baselines.PyGameMultiAgent.staticworld import StaticWorld

class Bot(object):
    alertRadius = 10

    def __init__(self, addr="127.0.0.1", serverport=9009):
        self.botport = random.randrange(8000, 8999)
        self.conn = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.conn.bind(("127.0.0.1", self.botport))
        self.addr = addr
        self.serverport = serverport

        self.read_list = [self.conn]
        self.write_list = []

        self.map_index = 0
        self.world = StaticWorld('../Maps/map_0.csv')
        self.running = True

    def run(self):
        self.conn.sendto("cb".encode('utf-8'), (self.addr, self.serverport))

        while self.running:
            msg, addr = self.conn.recvfrom(2048)
            msg = msg.decode('utf-8')  # Coordinates of all players
            AllZombiePose = []

            splitted_msg = msg.split('|')
            x, y, a, _ = splitted_msg[0].split(',')
            x = float(x)
            y = float(y)
            a = float(a)
            self_pos = (x, y, a)

            for position in msg.split('|')[1:-1]:
                x, y, angle, tag = position.split(',')
                x = float(x)
                y = float(y)
                angle = float(angle)
                tag = int(tag)
                if tag == 0:
                    AllZombiePose.append((x, y, angle))

            server_map_index = int(splitted_msg[-1])
            if server_map_index != self.map_index:
                del self.world
                self.world = StaticWorld("../Maps/map_{0}.csv".format(server_map_index))
                self.map_index = server_map_index

            movement = self.dummy_escape_policy(self_pos, AllZombiePose)
            self.conn.sendto(movement.encode('utf-8'), (self.addr, self.serverport))

    def dummy_escape_policy(self, self_pos, zombies):
        dir_score = [0 for _ in range(24)]
        x, y, angle = self_pos
        zombie_in_sight = False
        for z in zombies:
            zx, zy, zangle = z
            relative_angle = degrees(atan2(zy - y, zx - x))
            if relative_angle < 0:
                relative_angle += 360 #[0, 360]
            center_sector = round(relative_angle / 15)
            z_distance_sqr = (zx - x)**2 + (zy - y)**2

            for sector in range(center_sector - 11, center_sector + 11):
                dir_score[sector % 24] -= 1 / ((abs(sector - center_sector) + 1) * z_distance_sqr)   #score

            if z_distance_sqr < Bot.alertRadius * Bot.alertRadius:
                zombie_in_sight = True
        input()
        if not zombie_in_sight:
            return "ui"

        for s in range(24):
            wangle = s * 15
            wallDistance = self.world.rayCastWall((x, y), wangle)

            if wallDistance < 2:
                dir_score[s] = -99999
            else:
                dir_score[s] -= 1 / self.world.rayCastWall((x, y), wangle) ** 2

        now_heading_index = round(degrees(angle) / 15) % 24

        best_index = dir_score.index(max(dir_score))

        if dir_score[now_heading_index] == max(dir_score):
            return "uu"
        else:
            # if best_index - now_heading_index < -12 or 0 < best_index - now_heading_index < 12:
            #     return "ul"
            # else:
            #     return "ur"
            angle_diff_rad = radians(abs(best_index - now_heading_index) * 15)
            if best_index > now_heading_index:
                return "ul" + str(angle_diff_rad)
            else:
                return "ur" + str(angle_diff_rad)


if __name__ == "__main__":
    b = Bot()

    def term_sig_handler(signum, frame):
        b.running = False
        b.conn.sendto("d".encode('utf-8'), (b.addr, b.serverport))

    signal.signal(signal.SIGTERM, term_sig_handler)

    b.run()