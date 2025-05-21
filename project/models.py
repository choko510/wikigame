from collections import defaultdict
from pykakasi import kakasi

# Game room management
rooms = {}
# Player management (player_id -> room_id)
player_rooms = {}
# Game state management
game_states = defaultdict(dict)

ALLOWED_DOMAIN = "wikipedia.org"

# Initialize kakasi
kks = kakasi()
