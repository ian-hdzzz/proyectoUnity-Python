
from mesa.time import RandomActivation
from mesa.space import MultiGrid
from mesa.datacollection import DataCollector
import mesa
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import pandas as pd
from enum import Enum
from typing import Dict, Tuple, Optional, List, Set
import random
from collections import deque

class Direction(Enum):
    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"

class CellType(Enum):
    NORMAL = "normal"
    EXIT = "exit"
    HOTSPOT = "hotspot"  # Initial fire locations

class FireState(Enum):
    CLEAR = 0
    SMOKE = 1
    FIRE = 2

class Wall:
    """Wall with health points - can be damaged by explosions"""

    def __init__(self, health: int = 2):
        self.health = health
        self.max_health = health

    def take_damage(self, damage: int = 1) -> bool:
        """Damage wall, return True if destroyed"""
        self.health = max(0, self.health - damage)
        return self.health == 0

    def is_destroyed(self) -> bool:
        return self.health <= 0

    def __str__(self):
        return f"Wall(hp:{self.health}/{self.max_health})"

class POI:
    """Point of Interest (victim) to be rescued"""

    def __init__(self, poi_id: int, x: int, y: int, is_false_alarm: bool = False):
        self.poi_id = poi_id
        self.x = x
        self.y = y
        self.is_false_alarm = is_false_alarm
        self.is_revealed = False
        self.is_rescued = False
        self.carried_by = None  # Firefighter carrying this POI

    def reveal(self):
        """Reveal if this is a real victim or false alarm"""
        self.is_revealed = True
        return not self.is_false_alarm

    def __str__(self):
        status = "rescued" if self.is_rescued else "active"
        return f"POI-{self.poi_id}({self.x},{self.y})-{status}"

class FirefighterAgent(mesa.Agent):
    """Firefighter agent with Flash Point mechanics"""

    def __init__(self, unique_id: int, model, x: int, y: int):
        super().__init__(unique_id, model)
    def __init__(self, model, x: int, y: int):
        super().__init__(model)
        self.x = x
        self.y = y
        self.pos = (x, y)  # Mesa 3.0.3 uses pos attribute
        self.action_points = 4  # Standard AP in Flash Point
        self.max_action_points = 4
        self.carrying_poi = None
        self.role = "unassigned"  # "rescuer" or "fire_fighter"
        self.target_poi = None
        self.target_exit = None

    def move_to(self, new_x: int, new_y: int) -> bool:
        """Move to adjacent cell if possible (costs 1 AP)"""
        if self.action_points <= 0:
            return False

        # Check if move is valid (adjacent and no wall blocking)
        if not self.model.can_move_between(self.x, self.y, new_x, new_y):
            return False

        # Move
        self.model.grid.move_agent(self, (new_x, new_y))
        self.x, self.y = new_x, new_y
        self.action_points -= 1
        return True

    def extinguish_fire(self) -> bool:
        """Extinguish fire/smoke in current cell (costs 1 AP)"""
        if self.action_points <= 0:
            return False

        cell_state = self.model.get_fire_state(self.x, self.y)
        if cell_state == FireState.FIRE:
            self.model.set_fire_state(self.x, self.y, FireState.SMOKE)
            self.action_points -= 1
            return True
        elif cell_state == FireState.SMOKE:
            self.model.set_fire_state(self.x, self.y, FireState.CLEAR)
            self.action_points -= 1
            return True

        return False

    def pickup_poi(self) -> bool:
        """Pick up POI in current cell (costs 1 AP)"""
        if self.action_points <= 0 or self.carrying_poi is not None:
            return False

        poi = self.model.get_poi_at(self.x, self.y)
        if poi and not poi.is_rescued:
            if not poi.is_revealed:
                is_real = poi.reveal()
                if not is_real:  # False alarm
                    self.model.remove_poi(poi)
                    self.action_points -= 1
                    return True

            self.carrying_poi = poi
            poi.carried_by = self
            self.action_points -= 1
            return True

        return False

    def drop_poi_at_exit(self) -> bool:
        """Drop carried POI at exit (if at exit location)"""
        if self.carrying_poi is None:
            return False

        if self.model.is_exit(self.x, self.y):
            self.carrying_poi.is_rescued = True
            self.carrying_poi.carried_by = None
            self.carrying_poi = None
            self.model.rescued_pois += 1
            return True

        return False

    def get_path_to(self, target_x: int, target_y: int) -> List[Tuple[int, int]]:
        """Get shortest path to target considering walls"""
        return self.model.find_path((self.x, self.y), (target_x, target_y))

    def step(self):
        """Agent behavior logic"""
        self.action_points = self.max_action_points  # Reset AP each turn

        # Assign role based on distance to nearest POI
        self._assign_role()

        if self.role == "rescuer":
            self._rescue_behavior()
        else:
            self._firefighting_behavior()

    def _assign_role(self):
        """Assign role based on proximity to POIs"""
        active_pois = [poi for poi in self.model.pois if not poi.is_rescued]

        if not active_pois:
            self.role = "fire_fighter"
            return

        # Calculate distances to all POIs
        min_distance = float('inf')
        for poi in active_pois:
            path = self.get_path_to(poi.x, poi.y)
            if path:
                distance = len(path)
                min_distance = min(min_distance, distance)

        # Get all firefighters and their distances
        all_firefighters = [agent for agent in self.model.schedule.agents
                           if isinstance(agent, FirefighterAgent)]

        # Sort firefighters by distance to nearest POI
        firefighter_distances = []
        for ff in all_firefighters:
            ff_min_dist = float('inf')
            for poi in active_pois:
                path = ff.get_path_to(poi.x, poi.y)
                if path:
                    ff_min_dist = min(ff_min_dist, len(path))
            firefighter_distances.append((ff, ff_min_dist))

        firefighter_distances.sort(key=lambda x: x[1])

        # Assign top 3 as rescuers, others as fire fighters
        top_3 = [ff for ff, _ in firefighter_distances[:3]]
        self.role = "rescuer" if self in top_3 else "fire_fighter"

    def _rescue_behavior(self):
        """Behavior for rescue-focused firefighters"""
        # If carrying POI, go to nearest exit
        if self.carrying_poi:
            exits = self.model.get_exits()
            if exits:
                nearest_exit = min(exits, key=lambda e: abs(e[0] - self.x) + abs(e[1] - self.y))
                path = self.get_path_to(nearest_exit[0], nearest_exit[1])
                if path and len(path) > 1:
                    next_pos = path[1]
                    if self.move_to(next_pos[0], next_pos[1]):
                        if self.model.is_exit(self.x, self.y):
                            self.drop_poi_at_exit()
            return

        # Find nearest POI
        active_pois = [poi for poi in self.model.pois if not poi.is_rescued and poi.carried_by is None]
        if active_pois:
            nearest_poi = min(active_pois, key=lambda p: abs(p.x - self.x) + abs(p.y - self.y))

            # Move towards POI
            if self.x == nearest_poi.x and self.y == nearest_poi.y:
                self.pickup_poi()
            else:
                path = self.get_path_to(nearest_poi.x, nearest_poi.y)
                if path and len(path) > 1:
                    next_pos = path[1]
                    self.move_to(next_pos[0], next_pos[1])

    def _firefighting_behavior(self):
        """Behavior for firefighting-focused firefighters"""
        # Prioritize fire over smoke
        fire_cells = self.model.get_cells_with_fire()
        smoke_cells = self.model.get_cells_with_smoke()

        target_cells = fire_cells if fire_cells else smoke_cells

        if target_cells:
            # Find nearest fire/smoke
            nearest = min(target_cells, key=lambda c: abs(c[0] - self.x) + abs(c[1] - self.y))

            # If at target, extinguish
            if self.x == nearest[0] and self.y == nearest[1]:
                self.extinguish_fire()
            else:
                # Move towards target
                path = self.get_path_to(nearest[0], nearest[1])
                if path and len(path) > 1:
                    next_pos = path[1]
                    self.move_to(next_pos[0], next_pos[1])

class FlashPointModel(mesa.Model):
    """Mesa model for Flash Point Fire Rescue simulation"""

    def __init__(self, width: int = 10, height: int = 8, num_firefighters: int = 5,
                 initial_pois: int = 6, wall_health: int = 2):
        super().__init__()

        self.width = width
        self.height = height
        self.wall_health = wall_health
        self.rescued_pois = 0
        self.explosion_count = 0

        # Grid setup
        self.grid = MultiGrid(width, height, torus=False)
        self.schedule = RandomActivation(self)

        # Game state
        self.fire_grid = np.zeros((height, width), dtype=int)  # 0=clear, 1=smoke, 2=fire
        self.cell_types = np.full((height, width), CellType.NORMAL)
        self.walls = {}  # {(x1,y1,x2,y2): Wall} for wall between cells
        self.pois: List[POI] = []

        # Initialize game elements
        self._setup_exits()
        self._create_walls()
        self._place_firefighters(num_firefighters)
        self._place_initial_fires()
        self._place_pois(initial_pois)

        # Data collection
        self.datacollector = DataCollector(
            model_reporters={
                "Fire_Cells": lambda m: len(m.get_cells_with_fire()),
                "Smoke_Cells": lambda m: len(m.get_cells_with_smoke()),
                "Rescued_POIs": "rescued_pois",
                "Active_POIs": lambda m: len([p for p in m.pois if not p.is_rescued]),
                "Intact_Walls": lambda m: sum(1 for w in m.walls.values() if not w.is_destroyed()),
                "Explosions": "explosion_count"
            },
            agent_reporters={
                "X": "x", "Y": "y", "Role": "role",
                "AP": "action_points", "Carrying_POI": lambda a: a.carrying_poi is not None
            }
        )

        self.datacollector.collect(self)

    def _setup_exits(self):
        """Setup exit locations (family setup: 4 exits at edges)"""
        exits = [(0, 3), (0, 4), (9, 3), (9, 4)]  # Left and right exits
        for x, y in exits:
            if 0 <= x < self.width and 0 <= y < self.height:
                self.cell_types[y, x] = CellType.EXIT

    def _create_walls(self):
        """Create walls between cells"""
        # Create interior walls
        for y in range(self.height):
            for x in range(self.width):
                # East wall
                if x < self.width - 1:
                    wall_key = (x, y, x+1, y)
                    self.walls[wall_key] = Wall(self.wall_health)

                # South wall
                if y < self.height - 1:
                    wall_key = (x, y, x, y+1)
                    self.walls[wall_key] = Wall(self.wall_health)

        # Add some interior walls for realistic layout
        interior_walls = [
            # Add some strategic walls to create rooms
            ((2, 1), (2, 2)), ((2, 2), (2, 3)),  # Vertical walls
            ((6, 1), (6, 2)), ((6, 2), (6, 3)),
            ((1, 2), (2, 2)), ((3, 2), (4, 2)),  # Horizontal walls
            ((5, 2), (6, 2)), ((7, 2), (8, 2)),
        ]

        for (x1, y1), (x2, y2) in interior_walls:
            if self._is_valid_wall(x1, y1, x2, y2):
                wall_key = self._get_wall_key(x1, y1, x2, y2)
                if wall_key not in self.walls:
                    self.walls[wall_key] = Wall(self.wall_health)

    def _place_firefighters(self, num_firefighters: int):
        """Place firefighters at starting positions"""
        # Start firefighters near exits
        start_positions = [(1, 3), (1, 4), (8, 3), (8, 4), (4, 0)]

        for i in range(min(num_firefighters, len(start_positions))):
            x, y = start_positions[i]
            firefighter = FirefighterAgent(self, x, y)
            self.grid.place_agent(firefighter, (x, y))
            self.schedule.add(firefighter)

    def _place_initial_fires(self):
        """Place initial fire markers (hotspots)"""
        hotspots = [(3, 3), (6, 4), (4, 6)]  # Example hotspot locations

        for x, y in hotspots:
            if 0 <= x < self.width and 0 <= y < self.height:
                self.fire_grid[y, x] = FireState.FIRE.value
                self.cell_types[y, x] = CellType.HOTSPOT

    def _place_pois(self, num_pois: int):
        """Place POIs randomly (some false alarms)"""
        available_positions = []
        for y in range(self.height):
            for x in range(self.width):
                if (self.fire_grid[y, x] == FireState.CLEAR.value and
                    self.cell_types[y, x] != CellType.EXIT and
                    not self._has_firefighter_at(x, y)):
                    available_positions.append((x, y))

        positions = random.sample(available_positions, min(num_pois, len(available_positions)))

        for i, (x, y) in enumerate(positions):
            # 30% chance of false alarm
            is_false_alarm = random.random() < 0.3
            poi = POI(i, x, y, is_false_alarm)
            self.pois.append(poi)

    def _has_firefighter_at(self, x: int, y: int) -> bool:
        """Check if there's a firefighter at position"""
        agents = self.grid.get_cell_list_contents([(x, y)])
        return any(isinstance(agent, FirefighterAgent) for agent in agents)

    def get_cell_at(self, x: int, y: int) -> Optional['CellAgent']:
        """Get cell information - compatibility method"""
        if 0 <= x < self.width and 0 <= y < self.height:
            return True  # Cell exists
        return None

    def get_fire_state(self, x: int, y: int) -> FireState:
        """Get fire state at position"""
        if 0 <= x < self.width and 0 <= y < self.height:
            return FireState(self.fire_grid[y, x])
        return FireState.CLEAR

    def set_fire_state(self, x: int, y: int, state: FireState):
        """Set fire state at position"""
        if 0 <= x < self.width and 0 <= y < self.height:
            self.fire_grid[y, x] = state.value

    def is_exit(self, x: int, y: int) -> bool:
        """Check if position is an exit"""
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.cell_types[y, x] == CellType.EXIT
        return False

    def get_exits(self) -> List[Tuple[int, int]]:
        """Get all exit positions"""
        exits = []
        for y in range(self.height):
            for x in range(self.width):
                if self.cell_types[y, x] == CellType.EXIT:
                    exits.append((x, y))
        return exits

    def get_poi_at(self, x: int, y: int) -> Optional[POI]:
        """Get POI at position"""
        for poi in self.pois:
            if poi.x == x and poi.y == y and not poi.is_rescued and poi.carried_by is None:
                return poi
        return None

    def remove_poi(self, poi: POI):
        """Remove POI from game (false alarm)"""
        if poi in self.pois:
            self.pois.remove(poi)

    def get_cells_with_fire(self) -> List[Tuple[int, int]]:
        """Get all cells with fire"""
        fire_cells = []
        for y in range(self.height):
            for x in range(self.width):
                if self.fire_grid[y, x] == FireState.FIRE.value:
                    fire_cells.append((x, y))
        return fire_cells

    def get_cells_with_smoke(self) -> List[Tuple[int, int]]:
        """Get all cells with smoke"""
        smoke_cells = []
        for y in range(self.height):
            for x in range(self.width):
                if self.fire_grid[y, x] == FireState.SMOKE.value:
                    smoke_cells.append((x, y))
        return smoke_cells

    def _get_wall_key(self, x1: int, y1: int, x2: int, y2: int) -> Tuple[int, int, int, int]:
        """Get normalized wall key"""
        if x1 == x2:  # Horizontal wall
            return (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
        else:  # Vertical wall
            return (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))

    def _is_valid_wall(self, x1: int, y1: int, x2: int, y2: int) -> bool:
        """Check if wall position is valid"""
        return (0 <= x1 < self.width and 0 <= y1 < self.height and
                0 <= x2 < self.width and 0 <= y2 < self.height and
                ((abs(x1 - x2) == 1 and y1 == y2) or (abs(y1 - y2) == 1 and x1 == x2)))

    def has_wall_between(self, x1: int, y1: int, x2: int, y2: int) -> bool:
        """Check if there's an intact wall between two cells"""
        wall_key = self._get_wall_key(x1, y1, x2, y2)
        wall = self.walls.get(wall_key)
        return wall is not None and not wall.is_destroyed()

    def can_move_between(self, x1: int, y1: int, x2: int, y2: int) -> bool:
        """Check if movement is possible between adjacent cells"""
        # Check bounds
        if not (0 <= x2 < self.width and 0 <= y2 < self.height):
            return False

        # Check adjacency
        if abs(x1 - x2) + abs(y1 - y2) != 1:
            return False

        # Check wall
        return not self.has_wall_between(x1, y1, x2, y2)

    def find_path(self, start: Tuple[int, int], goal: Tuple[int, int]) -> List[Tuple[int, int]]:
        """BFS pathfinding considering walls"""
        if start == goal:
            return [start]

        queue = deque([(start, [start])])
        visited = {start}

        while queue:
            (x, y), path = queue.popleft()

            # Check all adjacent cells
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nx, ny = x + dx, y + dy

                if (nx, ny) not in visited and self.can_move_between(x, y, nx, ny):
                    new_path = path + [(nx, ny)]

                    if (nx, ny) == goal:
                        return new_path

                    queue.append(((nx, ny), new_path))
                    visited.add((nx, ny))

        return []  # No path found

    def spread_fire(self):
        """Simulate fire spread each turn"""
        # Simple fire spread: smoke becomes fire, fire spreads to adjacent clear cells
        new_fire_grid = self.fire_grid.copy()

        for y in range(self.height):
            for x in range(self.width):
                current_state = FireState(self.fire_grid[y, x])

                if current_state == FireState.SMOKE:
                    # Smoke has chance to become fire
                    if random.random() < 0.3:
                        new_fire_grid[y, x] = FireState.FIRE.value

                elif current_state == FireState.FIRE:
                    # Fire spreads to adjacent clear cells
                    for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                        nx, ny = x + dx, y + dy
                        if (0 <= nx < self.width and 0 <= ny < self.height and
                            self.fire_grid[ny, nx] == FireState.CLEAR.value):

                            if not self.has_wall_between(x, y, nx, ny):
                                if random.random() < 0.2:  # 20% chance to spread
                                    new_fire_grid[ny, nx] = FireState.SMOKE.value

        self.fire_grid = new_fire_grid

    def check_explosions(self):
        """Check for explosions (when fire reaches certain conditions)"""
        # Simple explosion logic: fire + fire in hotspot has chance to explode
        for y in range(self.height):
            for x in range(self.width):
                if (self.fire_grid[y, x] == FireState.FIRE.value and
                    self.cell_types[y, x] == CellType.HOTSPOT and
                    random.random() < 0.1):  # 10% explosion chance per turn at hotspots

                    self._trigger_explosion(x, y)

    def _trigger_explosion(self, x: int, y: int):
        """Trigger explosion at position"""
        self.explosion_count += 1

        # Damage walls around explosion
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.width and 0 <= ny < self.height:
                wall_key = self._get_wall_key(x, y, nx, ny)
                if wall_key in self.walls:
                    self.walls[wall_key].take_damage(1)

        # Spread fire to adjacent cells
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (-1, -1), (1, -1), (-1, 1)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.width and 0 <= ny < self.height:
                if self.fire_grid[ny, nx] == FireState.CLEAR.value:
                    self.fire_grid[ny, nx] = FireState.SMOKE.value

    def step(self):
        """Model step"""
        # Agent actions
        self.schedule.step()

        # Fire spread
        self.spread_fire()

        # Check for explosions
        self.check_explosions()

        # Collect data
        self.datacollector.collect(self)

class FlashPointVisualizer:
    """Visualizer for Flash Point simulation"""

    def __init__(self, model: FlashPointModel):
        self.model = model

    def plot_game_state(self, figsize=(12, 10), show_paths=False):
        """Plot current game state"""
        fig, ax = plt.subplots(figsize=figsize)

        # Set up plot
        ax.set_xlim(-0.5, self.model.width - 0.5)
        ax.set_ylim(-0.5, self.model.height - 0.5)
        ax.set_aspect('equal')
        ax.invert_yaxis()

        # Draw cells with fire states
        for y in range(self.model.height):
            for x in range(self.model.width):
                fire_state = FireState(self.model.fire_grid[y, x])
                cell_type = self.model.cell_types[y, x]

                # Base cell color
                if cell_type == CellType.EXIT:
                    color = 'lightgreen'
                elif cell_type == CellType.HOTSPOT:
                    color = 'darkred'
                else:
                    color = 'lightgray'

                # Fire state overlay
                if fire_state == FireState.FIRE:
                    color = 'red'
                elif fire_state == FireState.SMOKE:
                    color = 'gray'

                rect = patches.Rectangle((x - 0.4, y - 0.4), 0.8, 0.8,
                                       facecolor=color, alpha=0.7, edgecolor='black')
                ax.add_patch(rect)

        # Draw walls
        wall_thickness = 0.08
        for (x1, y1, x2, y2), wall in self.model.walls.items():
            if not wall.is_destroyed():
                # Determine wall position and orientation
                if x1 == x2:  # Vertical wall
                    wall_x = x1 - wall_thickness/2
                    wall_y = min(y1, y2) + 0.5 - wall_thickness/2
                    width, height = wall_thickness, wall_thickness
                else:  # Horizontal wall
                    wall_x = min(x1, x2) + 0.5 - wall_thickness/2
                    wall_y = y1 - wall_thickness/2
                    width, height = wall_thickness, wall_thickness

                # Color based on health
                if wall.health == wall.max_health:
                    wall_color = 'black'
                else:
                    wall_color = 'brown'

                wall_rect = patches.Rectangle((wall_x, wall_y), width, height,
                                            facecolor=wall_color, edgecolor='black')
                ax.add_patch(wall_rect)

        # Draw POIs
        for poi in self.model.pois:
            if not poi.is_rescued and poi.carried_by is None:
                circle = patches.Circle((poi.x, poi.y), 0.15,
                                      facecolor='yellow' if poi.is_revealed else 'orange',
                                      edgecolor='black', linewidth=2)
                ax.add_patch(circle)
                ax.text(poi.x, poi.y - 0.25, f'P{poi.poi_id}', ha='center', fontsize=8)

        # Draw firefighters
        colors = ['blue', 'cyan', 'magenta', 'purple', 'navy']
        for i, agent in enumerate(self.model.schedule.agents):
            if isinstance(agent, FirefighterAgent):
                color = colors[i % len(colors)]

                # Draw firefighter
                triangle = patches.RegularPolygon((agent.x, agent.y), 0.2,
                                                facecolor=color, edgecolor='black', linewidth=2)
                ax.add_patch(triangle)

                # Show role
                role_text = 'R' if agent.role == 'rescuer' else 'F'
                ax.text(agent.x, agent.y + 0.3, f'FF{i}-{role_text}',
                       ha='center', fontsize=8, weight='bold')

                # Show if carrying POI
                if agent.carrying_poi:
                    ax.text(agent.x, agent.y - 0.3, f'→P{agent.carrying_poi.poi_id}',
                           ha='center', fontsize=7, color='yellow', weight='bold')

        # Add legend
        legend_elements = [
            patches.Patch(color='red', label='Fire'),
            patches.Patch(color='gray', label='Smoke'),
            patches.Patch(color='lightgreen', label='Exit'),
            patches.Patch(color='darkred', label='Hotspot'),
            patches.Circle((0, 0), 0.1, facecolor='yellow', label='POI (revealed)'),
            patches.Circle((0, 0), 0.1, facecolor='orange', label='POI (hidden)'),
            patches.RegularPolygon((0, 0), 0.1, facecolor='blue', label='Firefighter'),
            patches.Rectangle((0, 0), 0.1, 0.1, facecolor='black', label='Intact Wall'),
            patches.Rectangle((0, 0), 0.1, 0.1, facecolor='brown', label='Damaged Wall')
        ]
        ax.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(1, 1))

        ax.set_title(f'Flash Point: Fire Rescue - Step {self.model.schedule.steps}\n'
                    f'Rescued: {self.model.rescued_pois}, Active POIs: {len([p for p in self.model.pois if not p.is_rescued])}, '
                    f'Fires: {len(self.model.get_cells_with_fire())}, Explosions: {self.model.explosion_count}')
        ax.set_xlabel('X Coordinate')
        ax.set_ylabel('Y Coordinate')
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        return fig, ax

    def plot_firefighter_roles(self, figsize=(10, 6)):
        """Plot firefighter role assignments over time"""
        model_df = self.model.datacollector.get_model_vars_dataframe()
        agent_df = self.model.datacollector.get_agent_vars_dataframe()

        if agent_df.empty:
            return None, None

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)

        # Plot 1: Role distribution over time
        role_counts = agent_df.groupby(['Step', 'Role']).size().unstack(fill_value=0)
        role_counts.plot(kind='area', ax=ax1, alpha=0.7)
        ax1.set_title('Firefighter Role Distribution Over Time')
        ax1.set_xlabel('Simulation Step')
        ax1.set_ylabel('Number of Firefighters')
        ax1.legend(title='Role')

        # Plot 2: Game progress
        ax2.plot(model_df.index, model_df['Rescued_POIs'], 'g-', label='Rescued POIs', linewidth=2)
        ax2.plot(model_df.index, model_df['Active_POIs'], 'orange', label='Active POIs', linewidth=2)
        ax2.plot(model_df.index, model_df['Fire_Cells'], 'r-', label='Fire Cells', linewidth=2)
        ax2.plot(model_df.index, model_df['Smoke_Cells'], 'gray', label='Smoke Cells', linewidth=2)

        ax2.set_title('Game Progress')
        ax2.set_xlabel('Simulation Step')
        ax2.set_ylabel('Count')
        ax2.legend()
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()
        return fig, (ax1, ax2)

    def plot_wall_damage_over_time(self, figsize=(10, 4)):
        """Plot wall damage statistics over time"""
        model_df = self.model.datacollector.get_model_vars_dataframe()

        fig, ax = plt.subplots(figsize=figsize)

        ax.plot(model_df.index, model_df['Intact_Walls'], 'g-', label='Intact Walls', linewidth=2)
        total_walls = len(self.model.walls)
        destroyed_walls = total_walls - model_df['Intact_Walls']
        ax.plot(model_df.index, destroyed_walls, 'r-', label='Destroyed Walls', linewidth=2)
        ax.plot(model_df.index, model_df['Explosions'], 'orange', label='Total Explosions', linewidth=2)

        ax.set_title('Wall Damage Over Time')
        ax.set_xlabel('Simulation Step')
        ax.set_ylabel('Count')
        ax.legend()
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        return fig, ax

# Example usage and simulation
def run_flashpoint_simulation(steps: int = 50, visualize_every: int = 10):
    """Run a complete Flash Point simulation with periodic visualization"""

    # Create model
    model = FlashPointModel(width=10, height=8, num_firefighters=5, initial_pois=6)
    visualizer = FlashPointVisualizer(model)

    print("Starting Flash Point: Fire Rescue Simulation")
    print(f"Initial state: {len(model.pois)} POIs, {len(model.get_cells_with_fire())} fire cells")

    # Initial visualization
    fig, ax = visualizer.plot_game_state()
    plt.show()

    # Run simulation
    for step in range(steps):
        model.step()

        # Periodic visualization
        if step % visualize_every == 0:
            print(f"\nStep {step}:")
            print(f"  Rescued POIs: {model.rescued_pois}")
            print(f"  Active POIs: {len([p for p in model.pois if not p.is_rescued])}")
            print(f"  Fire cells: {len(model.get_cells_with_fire())}")
            print(f"  Smoke cells: {len(model.get_cells_with_smoke())}")
            print(f"  Explosions: {model.explosion_count}")

            # Show current state
            fig, ax = visualizer.plot_game_state()
            plt.show()

        # Check win/loss conditions
        active_pois = [p for p in model.pois if not p.is_rescued]
        if not active_pois:
            print(f"\n🎉 VICTORY! All POIs rescued in {step} steps!")
            break

        if len(model.get_cells_with_fire()) > 15:  # Too much fire
            print(f"\n💥 DEFEAT! Fire spread too much at step {step}")
            break

    # Final analysis
    print("\n" + "="*50)
    print("SIMULATION COMPLETE")
    print("="*50)

    # Plot final statistics
    role_fig, role_axes = visualizer.plot_firefighter_roles()
    wall_fig, wall_ax = visualizer.plot_wall_damage_over_time()

    if role_fig:
        plt.show()
    plt.show()

    # Summary statistics
    final_data = model.datacollector.get_model_vars_dataframe()
    agent_data = model.datacollector.get_agent_vars_dataframe()

    print(f"Final Statistics:")
    print(f"  Total POIs rescued: {model.rescued_pois}")
    print(f"  POIs remaining: {len([p for p in model.pois if not p.is_rescued])}")
    print(f"  Total explosions: {model.explosion_count}")
    print(f"  Final fire cells: {len(model.get_cells_with_fire())}")
    print(f"  Walls destroyed: {len(model.walls) - sum(1 for w in model.walls.values() if not w.is_destroyed())}")

    return model, final_data, agent_data

# Quick test function
def quick_test():
    """Quick test of the Flash Point system"""
    model = FlashPointModel(width=8, height=6, num_firefighters=3, initial_pois=4)
    visualizer = FlashPointVisualizer(model)

    print("=== QUICK TEST ===")
    print(f"Created {len(model.schedule.agents)} firefighters")
    print(f"Placed {len(model.pois)} POIs")
    print(f"Created {len(model.walls)} walls")
    print(f"Fire cells: {len(model.get_cells_with_fire())}")

    # Show initial state
    fig, ax = visualizer.plot_game_state()
    plt.title("Initial Game State")
    plt.show()

    # Run a few steps
    for i in range(5):
        model.step()
        print(f"Step {i+1}: Rescued={model.rescued_pois}, Fires={len(model.get_cells_with_fire())}")

    # Show after steps
    fig, ax = visualizer.plot_game_state()
    plt.title("After 5 Steps")
    plt.show()

    return model

if __name__ == "__main__":
    # Run quick test
    # test_model = quick_test()

    # Uncomment to run full simulation
    model, final_data, agent_data = run_flashpoint_simulation(steps=30, visualize_every=5)