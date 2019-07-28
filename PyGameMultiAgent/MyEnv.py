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
        self.map_index = 0
        self.world = StaticWorld('Maps/map_0.csv')
        self.clientport = random.randrange(8000, 8999)
        self.conn = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.conn.bind(("127.0.0.1", self.clientport))
        self.addr = "127.0.0.1"
        self.serverport = 9009
        self.conn.sendto("cz".encode('utf-8'), (self.addr, self.serverport))

        self.action_space = Discrete(4)
        self.observation_space = Box(low = 0, high=3, shape=(self.world.radar_length, 1), dtype=np.float)

        self.saved_self_pose = None
        self.saved_all_zombie_pose = None
        self.saved_rew = 0.0

        self.screen = None

        self.stepcount = 0


    #block if no data received
    def _fetch_pos_from_server(self):
        msg, addr = self.conn.recvfrom(2048)
        msg = msg.decode('utf-8')  # Coordinates of all players

        splitted_msg = msg.split('|')
        x, y, a, _ = splitted_msg[0].split(',')
        x = float(x)
        y = float(y)
        a = float(a)
        self_pos = (x, y, a)

        AllZombiePose = []
        for position in splitted_msg[1:-1]:
            x, y, angle, tag = position.split(',')
            x = float(x)
            y = float(y)
            angle = float(angle)
            tag = int(tag)
            AllZombiePose.append((x, y, angle, tag))

        map_index = int(splitted_msg[-1])

        return self_pos, AllZombiePose, map_index

    def _calculate_reward(self, self_pos, AllZombiePose, last_self_pose, last_allZombiePose):
        if last_allZombiePose is None:
            return 0, False

        old_distance, _ = self._get_closest_bot_distance(last_self_pose, last_allZombiePose)
        curr_distance, _ = self._get_closest_bot_distance(self_pos, AllZombiePose)

        rew = 0

        # reward for approaching target
        if max(old_distance, curr_distance) < self.world.perception_grids:
            if curr_distance < old_distance:
                rew += (old_distance - curr_distance) * 0.5

        # reward for moving , weight 0.1 => 0.05
        old_x, old_y, _ = last_self_pose
        x, y, _ = self_pos
        dist = np.sqrt(np.square(x - old_x) + np.square(y - old_y))
        rew += dist * 0.01   # range[0, 0.05]

        # reward for staying near
        if curr_distance < Bot.alertRadius:
            blocked_distance = self._projection_blocking_distance(self_pos, AllZombiePose)
            clipped_curr_distance = max(2, curr_distance)

            rew += (1 / max(2, blocked_distance) - 1 / clipped_curr_distance)

        # reward for catching
        if curr_distance < 2:
            rew += 10
            return rew, True

        return rew, False

    def _projection_blocking_distance(self, self_pos, allActorPose):
        x, y, angle = self_pos
        distance, target = self._get_closest_bot_distance(self_pos, allActorPose)
        if distance > self.world.perception_grids or target is None:
            return 0

        target_x, target_y, _, _ = target
        me_to_target = np.asarray([target_x - x, target_y - y])
        me_to_target_unit = me_to_target / np.linalg.norm(me_to_target)

        maximum_proj_length = 0

        for actor in allActorPose:
            ax, ay, aa, atag = actor
            if atag == 0 and (x != ax or y != ay):
                actor_to_target = np.asarray([target_x - ax, target_y - ay])
                actor_proj_len = np.dot(me_to_target_unit, actor_to_target)
                if 0 < actor_proj_len < distance:
                    maximum_proj_length = max(maximum_proj_length, actor_proj_len)
        return maximum_proj_length

    def _get_closest_bot_distance(self, self_pos, allZombiePose):
        x, y, _ = self_pos
        closest_dist_sqr = 100000000
        target_actor = None
        for actor in allZombiePose:
            ax, ay, _, atag = actor
            if atag == 1:
                dist_sqr = (ax - x)**2 + (ay - y)**2
                if dist_sqr < closest_dist_sqr:
                    closest_dist_sqr = dist_sqr
                    target_actor = actor
        return np.sqrt(closest_dist_sqr), target_actor

    #returns (obs, reward, finish)
    def step(self, action):
        cmd = None
        if action == 0:
            cmd = "uu"
        elif action == 1:
            cmd = "ui"
        elif action == 2:
            cmd = "ul"
        else:
            cmd = "ur"
        cmd += "|"
        cmd += str(self.saved_rew)

        # For Manual debugging

        # if self.saved_self_pose is not None:
        #     print(self.saved_self_pose)
        #     print(self.world.to_local_radar_obs(self.saved_self_pose, self.saved_all_zombie_pose)[:, 0])
        #     cmd = input('please input cmd')
        # else:
        #     cmd = 'ui'
        self.conn.sendto(cmd.encode('utf-8'), (self.addr, self.serverport))

        self_pos, AllZombiePos, server_map_index = self._fetch_pos_from_server()
        if self.map_index != server_map_index:
            del self.world
            self.world = StaticWorld("Maps/map_{0}.csv".format(server_map_index))
            self.map_index = server_map_index

        rew, done = self._calculate_reward(self_pos, AllZombiePos, self.saved_self_pose, self.saved_all_zombie_pose)
        self.saved_self_pose = self_pos
        self.saved_all_zombie_pose = AllZombiePos
        self.saved_rew = rew

        #if done or self.stepcount == 4000:
        #    self.reset()

        done = done or self.stepcount == 4000

        self.stepcount += 1

        # return self.world.to_local_obs(self_pos, AllZombiePos), rew, done, {'episode': {'r':rew, 'l':self.stepcount}}
        return self.world.to_local_radar_obs(self_pos, AllZombiePos), rew, done, {'episode': {'r': rew, 'l': self.stepcount}}

    def reset(self):
        self.conn.sendto("r".encode('utf-8'), (self.addr, self.serverport))
        self_pos, AllZombiePos, server_map_index = self._fetch_pos_from_server()
        if self.map_index != server_map_index:
            del self.world
            self.world = StaticWorld("Maps/map_{0}.csv".format(server_map_index))
            self.map_index = server_map_index

        self.stepcount = 0
        return self.world.to_local_radar_obs(self_pos, AllZombiePos)

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