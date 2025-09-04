from flask import Flask, request, jsonify
from flask_cors import CORS
import json
from your_flashpoint_model import FlashPointModel, FirefighterAgent, FireState, CellType, POI

app = Flask("Python-Server")
CORS(app)  # Permite conexiones desde Unity

# Instancia global del modelo
current_model = None

@app.route('/api/test', methods=['GET'])
def test_api():
    return {"message": "Hello from Flash Point API!", "status": "CONNECTED"}

@app.route('/api/game/create', methods=['POST'])
def create_game():
    """Crear una nueva simulación"""
    global current_model
    
    try:
        data = request.json
        width = data.get('width', 10)
        height = data.get('height', 8)
        num_firefighters = data.get('num_firefighters', 5)
        initial_pois = data.get('initial_pois', 6)
        
        current_model = FlashPointModel(
            width=width, 
            height=height, 
            num_firefighters=num_firefighters,
            initial_pois=initial_pois
        )
        
        return jsonify({
            "status": "success",
            "message": "Game created successfully",
            "game_id": 1,
            "initial_state": get_game_state()
        })
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/game/state', methods=['GET'])
def get_current_state():
    """Obtener el estado actual del juego"""
    if current_model is None:
        return jsonify({"status": "error", "message": "No game created"}), 404
    
    return jsonify({
        "status": "success",
        "state": get_game_state()
    })

@app.route('/api/game/step', methods=['POST'])
def execute_step():
    """Ejecutar un paso de la simulación"""
    global current_model
    
    if current_model is None:
        return jsonify({"status": "error", "message": "No game created"}), 404
    
    try:
        # Ejecutar un paso
        current_model.step()
        
        return jsonify({
            "status": "success",
            "message": f"Step {current_model.schedule.steps} executed",
            "state": get_game_state()
        })
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/game/steps/<int:num_steps>', methods=['POST'])
def execute_multiple_steps(num_steps):
    """Ejecutar múltiples pasos"""
    global current_model
    
    if current_model is None:
        return jsonify({"status": "error", "message": "No game created"}), 404
    
    try:
        for _ in range(num_steps):
            current_model.step()
        
        return jsonify({
            "status": "success",
            "message": f"{num_steps} steps executed",
            "current_step": current_model.schedule.steps,
            "state": get_game_state()
        })
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/firefighters', methods=['GET'])
def get_firefighters():
    """Obtener información de todos los bomberos"""
    if current_model is None:
        return jsonify({"status": "error", "message": "No game created"}), 404
    
    firefighters = []
    for agent in current_model.schedule.agents:
        if isinstance(agent, FirefighterAgent):
            firefighters.append({
                "id": agent.unique_id,
                "position": {"x": agent.x, "y": agent.y},
                "action_points": agent.action_points,
                "max_action_points": agent.max_action_points,
                "role": agent.role,
                "carrying_poi": agent.carrying_poi.poi_id if agent.carrying_poi else None,
                "carrying_poi_position": {
                    "x": agent.carrying_poi.x, 
                    "y": agent.carrying_poi.y
                } if agent.carrying_poi else None
            })
    
    return jsonify({
        "status": "success",
        "firefighters": firefighters
    })

@app.route('/api/firefighter/<int:firefighter_id>/move', methods=['POST'])
def move_firefighter(firefighter_id):
    """Mover un bombero específico"""
    if current_model is None:
        return jsonify({"status": "error", "message": "No game created"}), 404
    
    try:
        data = request.json
        target_x = data['x']
        target_y = data['y']
        
        # Encontrar el bombero
        firefighter = None
        for agent in current_model.schedule.agents:
            if isinstance(agent, FirefighterAgent) and agent.unique_id == firefighter_id:
                firefighter = agent
                break
        
        if not firefighter:
            return jsonify({"status": "error", "message": "Firefighter not found"}), 404
        
        # Intentar mover
        success = firefighter.move_to(target_x, target_y)
        
        return jsonify({
            "status": "success" if success else "failed",
            "message": "Move successful" if success else "Move failed (no AP or blocked)",
            "firefighter": {
                "id": firefighter.unique_id,
                "position": {"x": firefighter.x, "y": firefighter.y},
                "action_points": firefighter.action_points
            }
        })
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/firefighter/<int:firefighter_id>/extinguish', methods=['POST'])
def extinguish_fire(firefighter_id):
    """Hacer que un bombero extinga fuego"""
    if current_model is None:
        return jsonify({"status": "error", "message": "No game created"}), 404
    
    try:
        # Encontrar el bombero
        firefighter = None
        for agent in current_model.schedule.agents:
            if isinstance(agent, FirefighterAgent) and agent.unique_id == firefighter_id:
                firefighter = agent
                break
        
        if not firefighter:
            return jsonify({"status": "error", "message": "Firefighter not found"}), 404
        
        # Intentar extinguir
        success = firefighter.extinguish_fire()
        
        return jsonify({
            "status": "success" if success else "failed",
            "message": "Fire extinguished" if success else "No fire to extinguish or no AP",
            "firefighter": {
                "id": firefighter.unique_id,
                "action_points": firefighter.action_points
            },
            "cell_state": current_model.get_fire_state(firefighter.x, firefighter.y).name
        })
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/pois', methods=['GET'])
def get_pois():
    """Obtener información de todas las POIs"""
    if current_model is None:
        return jsonify({"status": "error", "message": "No game created"}), 404
    
    pois = []
    for poi in current_model.pois:
        pois.append({
            "id": poi.poi_id,
            "position": {"x": poi.x, "y": poi.y},
            "is_revealed": poi.is_revealed,
            "is_false_alarm": poi.is_false_alarm if poi.is_revealed else None,
            "is_rescued": poi.is_rescued,
            "carried_by": poi.carried_by.unique_id if poi.carried_by else None
        })
    
    return jsonify({
        "status": "success",
        "pois": pois,
        "rescued_count": current_model.rescued_pois
    })

@app.route('/api/grid/fire', methods=['GET'])
def get_fire_grid():
    """Obtener el estado del fuego en toda la grilla"""
    if current_model is None:
        return jsonify({"status": "error", "message": "No game created"}), 404
    
    fire_grid = []
    for y in range(current_model.height):
        row = []
        for x in range(current_model.width):
            fire_state = FireState(current_model.fire_grid[y, x])
            cell_type = current_model.cell_types[y, x]
            
            row.append({
                "fire_state": fire_state.name,
                "fire_value": fire_state.value,
                "cell_type": cell_type.name,
                "is_exit": current_model.is_exit(x, y),
                "has_poi": current_model.get_poi_at(x, y) is not None
            })
        fire_grid.append(row)
    
    return jsonify({
        "status": "success",
        "fire_grid": fire_grid,
        "dimensions": {"width": current_model.width, "height": current_model.height}
    })

@app.route('/api/walls', methods=['GET'])
def get_walls():
    """Obtener información de todas las paredes"""
    if current_model is None:
        return jsonify({"status": "error", "message": "No game created"}), 404
    
    walls = []
    for (x1, y1, x2, y2), wall in current_model.walls.items():
        walls.append({
            "position": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
            "health": wall.health,
            "max_health": wall.max_health,
            "is_destroyed": wall.is_destroyed()
        })
    
    return jsonify({
        "status": "success",
        "walls": walls
    })

@app.route('/api/game/stats', methods=['GET'])
def get_game_stats():
    """Obtener estadísticas generales del juego"""
    if current_model is None:
        return jsonify({"status": "error", "message": "No game created"}), 404
    
    return jsonify({
        "status": "success",
        "stats": {
            "current_step": current_model.schedule.steps,
            "rescued_pois": current_model.rescued_pois,
            "active_pois": len([p for p in current_model.pois if not p.is_rescued]),
            "fire_cells": len(current_model.get_cells_with_fire()),
            "smoke_cells": len(current_model.get_cells_with_smoke()),
            "explosion_count": current_model.explosion_count,
            "intact_walls": sum(1 for w in current_model.walls.values() if not w.is_destroyed())
        }
    })

def get_game_state():
    """Función helper para obtener el estado completo del juego"""
    if current_model is None:
        return None
    
    # Obtener bomberos
    firefighters = []
    for agent in current_model.schedule.agents:
        if isinstance(agent, FirefighterAgent):
            firefighters.append({
                "id": agent.unique_id,
                "position": {"x": agent.x, "y": agent.y},
                "action_points": agent.action_points,
                "role": agent.role,
                "carrying_poi": agent.carrying_poi.poi_id if agent.carrying_poi else None
            })
    
    # Obtener POIs
    pois = []
    for poi in current_model.pois:
        pois.append({
            "id": poi.poi_id,
            "position": {"x": poi.x, "y": poi.y},
            "is_revealed": poi.is_revealed,
            "is_rescued": poi.is_rescued,
            "carried_by": poi.carried_by.unique_id if poi.carried_by else None
        })
    
    # Obtener grilla de fuego (simplificada)
    fire_data = []
    for y in range(current_model.height):
        row = []
        for x in range(current_model.width):
            fire_state = FireState(current_model.fire_grid[y, x])
            row.append({
                "fire_state": fire_state.name,
                "is_exit": current_model.is_exit(x, y)
            })
        fire_data.append(row)
    
    return {
        "step": current_model.schedule.steps,
        "dimensions": {"width": current_model.width, "height": current_model.height},
        "firefighters": firefighters,
        "pois": pois,
        "fire_grid": fire_data,
        "stats": {
            "rescued_pois": current_model.rescued_pois,
            "fire_cells": len(current_model.get_cells_with_fire()),
            "smoke_cells": len(current_model.get_cells_with_smoke()),
            "explosion_count": current_model.explosion_count
        }
    }

@app.route('/api/game/reset', methods=['POST'])
def reset_game():
    """Reiniciar el juego"""
    global current_model
    current_model = None
    
    return jsonify({
        "status": "success",
        "message": "Game reset successfully"
    })

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=3690, debug=True)