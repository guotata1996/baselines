import numpy as np
from pandas import read_csv
from math import floor, degrees, sin, cos, radians
import pygame

#Passable = 0 Wall = 1 #Zombie = 2

class StaticWorld:
    gridLength = 2  # how many GRIDs does a grid in csv map represent
    perception_grids = 15 # how far in GRIDs can actor see
    zoom = 8

    def __init__(self, csv_path):
        raw_data = np.asarray(read_csv(csv_path, skipinitialspace=True, header=None).values)[:,:-1] #dtype is char
        self.data = np.zeros_like(raw_data)

        for i in range(self.data.shape[0]):
            for j in range(self.data.shape[1]):
                if raw_data[i][j] == '#':
                    self.data[i][j] = 1

        self.length = self.data.shape[0] * self.gridLength
        self.width = self.data.shape[1] * self.gridLength

        self.image_wall = None
        self.image_zombie = None
        self.image_wall_1x1 = None
        self.image_zombie_1x1 = None
        self.image_bot = None

        self.local_length = (self.perception_grids * 2 + 1)
        self.local_width = (self.perception_grids * 2 + 1)

    def __getitem__(self, tup_item):
        _x, _y = tup_item
        grid_y = floor(_x // self.gridLength)
        grid_x = floor((self.length - _y - 1) // self.gridLength)

        #check if out of area
        if grid_x < 0 or grid_x >= self.data.shape[0] or grid_y < 0 or grid_y >= self.data.shape[1]:
            return 1
        return self.data[grid_x, grid_y]

    def draw_global(self, screen, poses_dict, rewards_dict):
        screen.fill(pygame.Color("black"))
        if self.image_wall is None:
            self.image_wall = pygame.image.load("../Resources/wall.png").convert_alpha()
            self.image_zombie = pygame.image.load("../Resources/sprite.PNG").convert_alpha()
            self.image_bot = pygame.image.load("../Resources/sprite_blue.png")

            self.image_wall = pygame.transform.rotozoom(self.image_wall, 0, self.zoom * self.gridLength / 10)
            self.image_zombie = pygame.transform.rotozoom(self.image_zombie, 0, self.zoom / 10)
            self.image_bot = pygame.transform.rotozoom(self.image_bot, 0, self.zoom / 10)


        for i in range(self.data.shape[1]):
            for j in range(self.data.shape[0]):
                if self.data[j][i] == 1:
                    screen.blit(self.image_wall, (i * self.gridLength * self.zoom, j * self.gridLength * self.zoom))

        for addr in list(poses_dict.keys()):
            pos = poses_dict[addr]

            x, y, angle, tag = pos
            if tag == 0:
                rot_image = pygame.transform.rotate(self.image_zombie, degrees(float(angle)))
            else:
                rot_image =  pygame.transform.rotate(self.image_bot, degrees(float(angle)))

            actor_position = (int(x * self.zoom), int((self.length - 1 - y) * self.zoom))
            screen.blit(rot_image, actor_position)

            if tag == 0 and addr in rewards_dict:
                rew = rewards_dict[addr]
                lo_rew_color = np.array([0, 0, 255])
                hi_rew_color = np.array([255, 0, 0])
                rew = 0.5 * np.clip(rew, -1, 1) + 0.5   #normalize to [0,1]
                interpolated_color = (1 - rew) * lo_rew_color + rew * hi_rew_color

                pygame.draw.circle(screen, interpolated_color, actor_position, int(self.zoom * self.perception_grids), 1)


    # free = 0
    # wall = 1
    # zombie = 2
    # player(bot) = 3
    def to_local_obs(self, pos, allZombiePose):
        obs = np.zeros((self.local_length, self.local_width), dtype = np.int)

        x, y, angle = pos
        local_frame_x_axis = np.asarray([sin(angle), -cos(angle)])
        local_frame_y_axis = np.asarray([cos(angle), sin(angle)])

        for local_frame_x in range(-self.perception_grids, self.perception_grids + 1):
            for local_frame_y in range(-self.perception_grids, self.perception_grids + 1):
                world_frame_x, world_frame_y = local_frame_x_axis * local_frame_x + local_frame_y_axis * local_frame_y
                world_frame_x += x
                world_frame_y += y

                if self.__getitem__((world_frame_x, world_frame_y)) == 1:
                    obs[local_frame_x + self.perception_grids][self.perception_grids - local_frame_y] = 1

        for a_zombie in allZombiePose:
            x1, y1, angle1, tag = a_zombie
            x1 -= x
            y1 -= y
            local_frame_x1 = int(sin(angle) * x1 - cos(angle) * y1)
            local_frame_y1 = int(cos(angle) * x1 + sin(angle) * y1)
            if -self.perception_grids <= local_frame_x1 <= self.perception_grids and \
                    -self.perception_grids <= local_frame_y1 <= self.perception_grids:
                obs[local_frame_x1 + self.perception_grids][self.perception_grids - local_frame_y1] = tag + 2

        return np.expand_dims(obs, axis=2)


    # also shows rotation
    def draw_local(self, screen, pos, allZombiePose):
        screen.fill((80, 200, 80))
        if self.image_wall is None:
            self.image_wall = pygame.image.load("../Resources/wall.png").convert_alpha()
            self.image_zombie = pygame.image.load("../Resources/point_10x10.png").convert_alpha()
            self.image_bot = pygame.image.load("../Resources/sprite_blue.png")

        x, y, angle = pos
        local_frame_x_axis = np.asarray([sin(angle), -cos(angle)])
        local_frame_y_axis = np.asarray([cos(angle), sin(angle)])

        for local_frame_x in range(-self.perception_grids, self.perception_grids + 1):
            for local_frame_y in range(-self.perception_grids, self.perception_grids + 1):
                world_frame_x, world_frame_y = local_frame_x_axis * local_frame_x + local_frame_y_axis * local_frame_y
                world_frame_x += x
                world_frame_y += y

                if self.__getitem__((world_frame_x, world_frame_y)) == 1:
                    screen.blit(self.image_wall,
                                (self.zoom * (local_frame_x + self.perception_grids),
                                 self.zoom * (self.perception_grids - local_frame_y)))

        for a_zombie in allZombiePose:
            x1, y1, angle1, tag = a_zombie
            x1 -= x
            y1 -= y
            local_frame_x1 = sin(angle) * x1 - cos(angle) * y1
            local_frame_y1 = cos(angle) * x1 + sin(angle) * y1

            if tag == 0:
                image = self.image_zombie
            else:
                image = self.image_bot

            relativeAngle = angle1 - angle
            rot_image = pygame.transform.rotate(image, degrees(relativeAngle))

            if -self.perception_grids <= local_frame_x1 <= self.perception_grids and \
                    -self.perception_grids <= local_frame_y1 <= self.perception_grids:
                screen.blit(rot_image,
                            (self.zoom * (local_frame_x1 + self.perception_grids),
                             self.zoom * (self.perception_grids - local_frame_y1)))

    #angle in degrees
    def rayCastWall(self, center, angle, distance = 15):
        for i in np.arange(0, distance, 0.5):
            if self.__getitem__((center[0] + cos(radians(angle)) * i, center[1] + sin(radians(angle)) * i)) == 1:
                return i
        return 99999
