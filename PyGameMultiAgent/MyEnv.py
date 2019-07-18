from gym.core import Env
from gym.spaces.box import Box
from gym.spaces.discrete import Discrete
from baselines.PyGameMultiAgent.staticworld import StaticWorld
import numpy as np
import pygame
import pygame.locals
import socket
import select
import random
from baselines.PyGameMultiAgent.bot import Bot
import time

class ZombieChasePlayerEnv(Env):

    def __init__(self):
        self.world = StaticWorld('Maps/map_0.csv')
        self.clientport = random.randrange(8000, 8999)
        self.conn = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.conn.bind(("127.0.0.1", self.clientport))
        self.addr = "127.0.0.1"
        self.serverport = 9009

        self.action_space = Discrete(4)
        self.observation_space = Box(low = 0, high=3, shape=(self.world.local_length, self.world.local_length, 1), dtype=np.uint8)
        self.saved_self_pose = None
        self.saved_all_zombie_pose = None

        self.screen = None

        self.stepcount = 0

        print('making MyEnv...,')

    #block if no data received
    def _fetch_pos_from_server(self):
        msg, addr = self.conn.recvfrom(2048)
        msg = msg.decode('utf-8')  # Coordinates of all players
        self_pos = None
        AllZombiePose = []

        for position in msg.split('|'):
            x, y, angle, tag = position.split(',')
            x = float(x)
            y = float(y)
            angle = float(angle)
            tag = int(tag)
            if self_pos is None:
                self_pos = (x, y, angle)
            AllZombiePose.append((x, y, angle, tag))

        self.saved_self_pose = self_pos
        self.saved_all_zombie_pose = AllZombiePose
        return self_pos, AllZombiePose

    def _calculate_reward(self, self_pos, AllZombiePose):
        x, y, _= self_pos
        total_rew = 0
        for actor in AllZombiePose:
            ax, ay, aangle, atag = actor
            if atag == 1 and (ax - x)**2 + (ay - y)**2 < Bot.GetAlertRadius() * Bot.GetAlertRadius():
                total_rew += 1 / max((ax - x)**2 + (ay - y)**2, 0.1)
                if (ax - x)**2 + (ay - y)**2 < 4:
                    return total_rew, True
        return total_rew, False


    #returns (obs, reward, finish)
    def step(self, action):
        if action == 0:
            self.conn.sendto("uu".encode('utf-8'), (self.addr, self.serverport))
        elif action == 1:
            self.conn.sendto("ui".encode('utf-8'), (self.addr, self.serverport))
        elif action == 2:
            self.conn.sendto("ul".encode('utf-8'), (self.addr, self.serverport))
        else:
            self.conn.sendto("ur".encode('utf-8'), (self.addr, self.serverport))
        self_pos, AllZombiePos = self._fetch_pos_from_server()
        rew, done = self._calculate_reward(self_pos, AllZombiePos)
        if done or self.stepcount == 4000:
            self.reset()

        self.stepcount += 1

        return self.world.to_local_obs(self_pos, AllZombiePos), rew, done, {'episode': {'r':rew, 'l':self.stepcount}}


    def reset(self):
        self.conn.sendto("d".encode('utf-8'), (self.addr, self.serverport))
        self.conn.sendto("cz".encode('utf-8'), (self.addr, self.serverport))
        self_pos, AllZombiePos = self._fetch_pos_from_server()
        self.stepcount = 0
        return self.world.to_local_obs(self_pos, AllZombiePos)

    metadata = {'render.modes': ['human', 'rgb_array']}

    def render(self, mode='human'):
        if self.saved_self_pose is not None:
            if mode == 'human':
                if self.screen == None:
                    self.screen = pygame.display.set_mode(
                        (self.world.local_width * self.world.zoom, self.world.local_length * self.world.zoom))
                self.world.draw_local(self.screen, self.saved_self_pose, self.saved_all_zombie_pose)
                pygame.display.update()
                return
        else:
            super(ZombieChasePlayerEnv, self).render(mode=mode)

    def close(self):
        self.conn.sendto("d".encode('utf-8'), (self.addr, self.serverport))
        if self.screen is not None:
            pygame.quit()

    def seed(self, seed=None):
        return [0]