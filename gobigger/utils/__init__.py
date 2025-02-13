from .structures import format_vector, add_size, save_screen_data_to_img, Border, QuadNode
from .collision_detection import create_collision_detection
from .precision_algorithm import precision_algorithm 

from .tool import *

Colors = [
        (153,51,250), # Lake Purple
        (65,105,225),
        (0,255,255),
        (0,0,255),
        (0,199,140),
        (255,0,255),
        (221,160,221),
        (163,148,128),
        (34,139,34),
        (112,128,105),
        (61,89,171),
        (255,69,0),
        (176,48,31),
        (255,192,203),
        (255,127,80),
        (240,230,140),
        (107,142,35),
        (255,235,205),
        (192,192,192),
        (250,235,215),
        (46,139,87),
        (160,21,240),
        (244,164,96),
        (3,168,158),
        (135,38,87),
        (199,97,20),
        (189,252,201),
        (106,90,205)
]

GRAY = (220, 220, 220)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
YELLOW = (255, 153, 18)
GREEN = (0, 255, 0)
PURPLE = (160, 32, 240)

PLAYER_COLORS = [
        (12,12,12),
        (24,24,24),
        (36,36,36),
        (48,48,48),
        (60,60,60),
        (72,72,72),
        (84,84,84),
        (96,96,96),
        (108,108,108),
        (120,120,120),
        (132,132,132),
        (144,144,144),
        (156,156,156),
        (168,168,168),
        (180,180,180),
        (192,192,192),
        (204,204,204),
        (216,216,216),
        (228,228,228),
        (240,240,240),
        (252,252,252),
]

FOOD_COLOR = (0,0,0)
THORNS_COLOR = (100,100,100)
SPORE_COLOR = (200,200,200)

