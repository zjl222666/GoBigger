import math
import logging
import random
import uuid
from abc import ABC, abstractmethod
from easydict import EasyDict
from pygame.math import Vector2

from .base_manager import BaseManager
from gobigger.utils import format_vector, Border
from gobigger.balls import FoodBall, ThornsBall, CloneBall, SporeBall


class FoodManager(BaseManager):

    def __init__(self, cfg, border):
        super(FoodManager, self).__init__(cfg, border)
        self.food_refresh_time = self.cfg.refresh_time
        self.refresh_time_count = 0

    def get_balls(self):
        return list(self.balls.values())
    
    def add_balls(self, balls):
        if isinstance(balls, list):
            for ball in balls:
                self.balls[ball.name] = ball
        elif isinstance(balls, FoodBall):
            self.balls[balls.name] = balls
        return True

    def refresh(self):
        todo_num = min(self.cfg.refresh_num, self.cfg.num_max - len(self.balls))
        for _ in range(todo_num):
            self.add_balls(self.spawn_ball())

    def remove_balls(self, balls):
        if isinstance(balls, list):
            for ball in balls:
                ball.remove()
                del self.balls[ball.name]
        elif isinstance(balls, FoodBall):
            balls.remove()
            del self.balls[balls.name]

    def spawn_ball(self):
        position = self.border.sample()
        size = random.uniform(self.ball_settings.radius_min, self.ball_settings.radius_max)**2
        name = uuid.uuid1()
        return FoodBall(name=name, position=position, border=self.border, size=size, **self.ball_settings)

    def init_balls(self):
        for _ in range(self.cfg.num_init):
            ball = self.spawn_ball()
            self.balls[ball.name] = ball

    def step(self, duration):
        self.refresh_time_count += duration
        if self.refresh_time_count >= self.food_refresh_time:
            self.refresh()
            self.refresh_time_count = 0

    def reset(self):
        self.refresh_time_count = 0
        self.balls = {}
        return True
