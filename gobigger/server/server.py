import random
from easydict import EasyDict
import uuid
import logging
import cv2
import os
import time
import numpy as np

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
os.environ['SDL_AUDIODRIVER'] = 'dsp'

from pygame.math import Vector2

from gobigger.utils import Border, create_collision_detection
from gobigger.balls import FoodBall, ThornsBall, CloneBall, SporeBall
from gobigger.managers import FoodManager, SporeManager, ThornsManager, PlayerManager


class Server:
    '''
    Overview:
        Server is responsible for the management of the entire game environment, including the status of all balls in the environment, and the status update after the action is entered
        The main logic when updating is as follows:
        0 tick -> input action -> update the state of the player's ball -> update the state of all balls after the current state continues for 1 tick
            -> detect collision and eating (update status) -> 0 tick end/1 tick start
        The details are as follows:
        1. Generate all balls (food, thorns, players)
        2. Single step
            1. Modify the current state of all players' balls according to the action (including acceleration, instantaneous state after splitting/spitting)
            2. Continue a tick for the current state of all balls, that is, update the acceleration/velocity/position of each ball after a tick, and at the same time the ball that is in the moving state in this tick
            3. Adjust all balls in each player (rigid body collision + ball-ball fusion)
            4. For each ball moved in this tick (already sorted by priority):
                1. We will know which balls he collided with (there will be repetitions)
                2. Category discussion
                    1. One of the balls is the player ball
                        1. Another is another player's ball, the bigger one eats the smaller one
                        2. The other side is your own clone, in fact, you don’t need to deal with it if you have already dealt with it before.
                        3. Another is food/spores, player ball eat it
                        4. Another is the thornball
                            1. Do not touch the center of the circle, continue
                            2. Hit the center of the circle
                                1. player ball is older than thornball
                                    1. number of player's avatar reaches the upper limit, thornball will be eaten
                                    2. number of player's avatar doesn't reache the upper limit, player ball eat thornball and blow up
                                2. player ball is younger than thornball, nothing happened
                    2. One of the balls is a thornball
                        1. Another is the player ball
                            1. hit the center of a circle
                                1. player ball is older than thornball
                                    1. number of player's avatar reaches the upper limit, thornball will be eaten
                                    2. number of player's avatar doesn't reache the upper limit, player ball eat thornball and blow up
                                2. player ball is younger than thornball, nothing happened
                            2. Do not touch the center of the circle, continue,
                        2. The another is the spore, thornball eat it and add a speed and acceleration
                    3. One of the balls is Spore
                        1. Another is the player ball, Spore was eaten
                        2. Another is the thorn ball, Spore was eaten
        3. After each tick, check if you want to update food, thorns, and player rebirth
    '''

    @staticmethod
    def default_config():
        cfg = dict(
            version='0.1',
            team_num=4, 
            player_num_per_team=3, 
            map_width=1000,
            map_height=1000, 
            match_time=60*10,
            state_tick_per_second=20, # frame
            action_tick_per_second=5, # frame
            collision_detection_type='precision', 
            manager_settings=dict(
                # food setting
                food_manager=dict(
                    num_init=2000, # initial number
                    num_min=2000, # Minimum number
                    num_max=2500, # Maximum number
                    refresh_time=2, # Time interval (seconds) for refreshing food in the map
                    refresh_num=30, # The number of refreshed foods in the map each time
                    ball_settings=dict( # The specific parameter description can be viewed in the ball module
                        radius_min=2, 
                        radius_max=2,
                    ),
                ),
                # thorns setting
                thorns_manager=dict(
                    num_init=15, # initial number
                    num_min=15, # Minimum number
                    num_max=20, # Maximum number
                    refresh_time=2, # Time interval (seconds) for refreshing thorns in the map
                    refresh_num=2, # The number of refreshed  thorns in the map each time
                    ball_settings=dict( # The specific parameter description can be viewed in the ball module
                        radius_min=12, 
                        radius_max=20, 
                        vel_max=100,
                        eat_spore_vel_init=10, 
                        eat_spore_vel_zero_time=1,
                    )
                ),
                # player setting
                player_manager=dict(
                    ball_settings=dict(  # The specific parameter description can be viewed in the ball module
                        acc_max=30, 
                        vel_max=20,
                        radius_min=3, 
                        radius_max=100, 
                        radius_init=3, 
                        part_num_max=16, 
                        on_thorns_part_num=10, 
                        on_thorns_part_radius_max=20,
                        split_radius_min=10, 
                        eject_radius_min=10, 
                        recombine_age=20,
                        split_vel_init=30,
                        split_vel_zero_time=1, 
                        stop_zero_time=1,
                        size_decay_rate=0.00005, 
                        given_acc_weight=10,
                    )
                ),
                # spore setting
                spore_manager=dict(
                    ball_settings=dict( # The specific parameter description can be viewed in the ball module
                        radius_min=3, 
                        radius_max=3, 
                        vel_init=250,
                        vel_zero_time=0.3, 
                        spore_radius_init=20, 
                    )
                )   
            )
        )
        return EasyDict(cfg)

    def __init__(self, cfg=None):
        self.cfg = Server.default_config()
        if isinstance(cfg, dict):
            cfg = EasyDict(cfg)
            self.cfg.update(cfg)
        logging.debug(self.cfg)
        self.team_num = self.cfg.team_num
        self.player_num_per_team = self.cfg.player_num_per_team
        self.map_width = self.cfg.map_width
        self.map_height = self.cfg.map_height
        self.match_time = self.cfg.match_time
        self.state_tick_per_second = self.cfg.state_tick_per_second
        self.action_tick_per_second = self.cfg.action_tick_per_second
        # other kwargs
        self.state_tick_duration = 1 / self.state_tick_per_second
        self.action_tick_duration = 1 / self.action_tick_per_second
        self.state_tick_per_action_tick = self.state_tick_per_second // self.action_tick_per_second
        
        self.border = Border(0, 0, self.map_width, self.map_height)
        self.last_time = 0
        self.screens_all = []
        self.screens_partial = {}

        self.food_manager = FoodManager(self.cfg.manager_settings.food_manager, border=self.border)
        self.thorns_manager = ThornsManager(self.cfg.manager_settings.thorns_manager, border=self.border)
        self.spore_manager = SporeManager(self.cfg.manager_settings.spore_manager, border=self.border)
        self.player_manager  = PlayerManager(self.cfg.manager_settings.player_manager, border=self.border,
                                             team_num=self.team_num, player_num_per_team=self.player_num_per_team, 
                                             spore_manager_settings=self.cfg.manager_settings.spore_manager)

        self.collision_detection_type = self.cfg.collision_detection_type
        self.collision_detection = create_collision_detection(self.collision_detection_type, border=self.border)

    def spawn_balls(self):
        '''
        Initialize all balls
        '''
        self.food_manager.init_balls() # init food
        self.thorns_manager.init_balls() # init thorns
        self.player_manager.init_balls() # init player

    def step_state_tick(self, actions=None):
        moving_balls = [] # Record all balls in motion
        total_balls = [] # Record all balls
        # Update all player balls according to action
        if actions is not None:
            '''
            In a single action: 
              If sporulation and splitting operations occur at the same time, sporulation will be given priority
              If move and stop move occur at the same time in action, perform stop move operation
            '''

            for player in self.player_manager.get_players():
                direction_x, direction_y, action_type = actions[player.name]
                if direction_x is None or direction_y is None:
                    direction = None
                else:
                    direction = Vector2(direction_x, direction_y).normalize()
                if action_type == 0: # spore
                    tmp_spore_balls = player.eject()
                    for tmp_spore_ball in tmp_spore_balls:
                        if tmp_spore_ball:
                            self.spore_manager.add_balls(tmp_spore_ball) 
                if action_type == 1: # split
                    self.player_manager.add_balls(player.split())
                if action_type == 2: # stop moving
                    player.stop()
                else: # move
                    player.move(direction=direction, duration=self.state_tick_duration)
                    moving_balls.extend(player.get_balls())
        else:
            for player in self.player_manager.get_players():
                player.move(duration=self.state_tick_duration)
                moving_balls.extend(player.get_balls())
                total_balls.extend(player.get_balls())
        moving_balls = sorted(moving_balls, reverse=True) # Sort by size
        # Update the status of other balls after moving, and record the balls with status updates
        for thorns_ball in self.thorns_manager.get_balls():
            if thorns_ball.moving:
                thorns_ball.move(duration=self.state_tick_duration)
            moving_balls.append(thorns_ball)
        for spore_ball in self.spore_manager.get_balls():
            if spore_ball.moving:
                spore_ball.move(duration=self.state_tick_duration)
        # Adjust the position of all player balls
        self.player_manager.adjust()
        # Collision detection
        total_balls.extend(self.player_manager.get_balls())
        total_balls.extend(self.thorns_manager.get_balls())
        total_balls.extend(self.spore_manager.get_balls())
        total_balls.extend(self.food_manager.get_balls())
        collisions_dict = self.collision_detection.solve(moving_balls, total_balls)
        # Process each ball in moving_balls
        for index, moving_ball in enumerate(moving_balls):
            if not moving_ball.is_remove and index in collisions_dict:
                for target_ball in collisions_dict[index]:
                    self.deal_with_collision(moving_ball, target_ball)
        # After each tick, check if there is a need to update food, thorns, and player rebirth
        self.food_manager.step(duration=self.state_tick_duration)
        self.spore_manager.step(duration=self.state_tick_duration)
        self.thorns_manager.step(duration=self.state_tick_duration)
        self.player_manager.step()
        self.last_time += self.state_tick_duration

    def deal_with_collision(self, moving_ball, target_ball):
        if not moving_ball.is_remove and not target_ball.is_remove: # Ensure that the two balls are present
            if isinstance(moving_ball, CloneBall): 
                if isinstance(target_ball, CloneBall):
                    if moving_ball.team_name != target_ball.team_name:
                        if moving_ball.size > target_ball.size:
                            moving_ball.eat(target_ball)
                            self.player_manager.remove_balls(target_ball)
                        else:
                            target_ball.eat(moving_ball)
                            self.player_manager.remove_balls(moving_ball)
                    elif moving_ball.owner != target_ball.owner:
                        if moving_ball.size > target_ball.size:
                            if self.player_manager.get_clone_num(target_ball) > 1:
                                moving_ball.eat(target_ball)
                                self.player_manager.remove_balls(target_ball)
                        else:
                            if self.player_manager.get_clone_num(moving_ball) > 1:
                                target_ball.eat(moving_ball)
                                self.player_manager.remove_balls(moving_ball)
                elif isinstance(target_ball, FoodBall):
                    moving_ball.eat(target_ball)
                    self.food_manager.remove_balls(target_ball)
                elif isinstance(target_ball, SporeBall):
                    moving_ball.eat(target_ball)
                    self.spore_manager.remove_balls(target_ball)
                elif isinstance(target_ball, ThornsBall):
                    if moving_ball.size > target_ball.size:
                        ret = moving_ball.eat(target_ball, clone_num=self.player_manager.get_clone_num(moving_ball))
                        self.thorns_manager.remove_balls(target_ball)
                        if isinstance(ret, list): 
                            self.player_manager.add_balls(ret) 
            elif isinstance(moving_ball, ThornsBall):
                if isinstance(target_ball, CloneBall):
                    if moving_ball.size < target_ball.size: 
                        ret = target_ball.eat(moving_ball, clone_num=self.player_manager.get_clone_num(target_ball))
                        self.thorns_manager.remove_balls(moving_ball)
                        if isinstance(ret, list): 
                            self.player_manager.add_balls(ret) 
                elif isinstance(target_ball, SporeBall): 
                    moving_ball.eat(target_ball)
                    self.spore_manager.remove_balls(target_ball)
            elif isinstance(moving_ball, ThornsBall):
                if isinstance(target_ball, CloneBall) or isinstance(target_ball, ThornsBall): 
                    target_ball.eat(moving_ball)
                    self.spore_manager.remove_balls(moving_ball)
        else:
            return

    def start(self):
        self.spawn_balls()
        self._end_flag = False

    def stop(self):
        self._end_flag = True

    def reset(self):
        self.last_time = 0
        self.screens_all = []
        self.screens_partial = {}
        self.food_manager.reset()
        self.thorns_manager.reset()
        self.spore_manager.reset()
        self.player_manager.reset()
        self.start()

    def step(self, actions=None, save_video=False, save_path=''):
        if self.last_time >= self.match_time:
            if save_video:
                self.save_mp4(save_path=save_path)
            self.stop()
            return True
        if not self._end_flag:
            for i in range(self.state_tick_per_action_tick):
                if i == 0:
                    self.step_state_tick(actions)
                    if save_video:
                        screen_data_all, screen_data_players = self.render.get_tick_all_colorful(
                            food_balls=self.food_manager.get_balls(),
                            thorns_balls=self.thorns_manager.get_balls(),
                            spore_balls=self.spore_manager.get_balls(),
                            players=self.player_manager.get_players())
                        self.screens_all.append(screen_data_all)
                        for player_name, screen_data_player in screen_data_players.items():
                            if player_name not in self.screens_partial:
                                self.screens_partial[player_name] = []
                            self.screens_partial[player_name].append(screen_data_player)
                else:
                    self.step_state_tick()
        return False

    def set_render(self, render):
        self.render = render

    def obs(self, obs_type='all'):
        assert obs_type in ['all', 'single']
        assert hasattr(self, 'render')
        team_name_size = self.player_manager.get_teams_size()
        global_state = {
            'border': [self.map_width, self.map_height],
            'total_time': self.match_time,
            'last_time': self.last_time,
            'leaderboard': {
                str(i): team_name_size[str(i)] for i in range(self.team_num)
            }
        }
        _, screen_data_players = self.render.update_all(food_balls=self.food_manager.get_balls(),
                                                        thorns_balls=self.thorns_manager.get_balls(),
                                                        spore_balls=self.spore_manager.get_balls(),
                                                        players=self.player_manager.get_players())
        return global_state, screen_data_players

    def save_mp4(self, save_path=''):
        video_id = time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime())
        fps = self.action_tick_per_second
        # save all
        video_file = os.path.join(save_path, '{}-all.mp4'.format(video_id))
        out = cv2.VideoWriter(video_file, cv2.VideoWriter_fourcc(*'MP4V'), fps, self.screens_all[0].shape[:2])
        for screen in self.screens_all:
            out.write(screen)
        out.release()
        cv2.destroyAllWindows()
        # save partial
        for player_name, screens in self.screens_partial.items():
            video_file = os.path.join(save_path, '{}-{:02d}.mp4'.format(video_id, int(player_name)))
            out = cv2.VideoWriter(video_file, cv2.VideoWriter_fourcc(*'MP4V'), fps, (300,300))
            for screen in screens:
                out.write(screen)
            out.release()
            cv2.destroyAllWindows()

    def get_player_names(self):
        return self.player_manager.get_player_names()

    def get_team_names(self):
        return self.player_manager.get_team_names()

    def get_player_names_with_team(self):
        return self.player_manager.get_player_names_with_team()

    def close(self):
        self.stop()
        if hasattr(self, 'render'):
            self.render.close()

    def seed(self, seed):
        self._seed = seed
        np.random.seed(self._seed)
        random.seed(self._seed)
