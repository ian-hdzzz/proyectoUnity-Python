# Dependencies

pip install numpy scipy matplotlib seaborn scikit-learn mesa==3.0.3 -q
pip install -r requirements.txt
 te va a pedir crear un ambiente, le pones que sí 
 y ya puedes correr el archivo de python (testApi.py)

# unity
los dos archivos de c# van en unity
en esta linea cambias la dirección por la que te de tu ac cuando ejecutes testApi.py
    public string serverURL = "http://localhost:3690"; 




# Flash Point Unity Setup Guide

## Configuración del Proyecto Unity

### 1. Configuración inicial
1. Crea un nuevo proyecto 3D en Unity
2. Instala TextMeshPro cuando Unity lo solicite
3. Configura la escena principal con una cámara isométrica

### 2. Estructura de GameObjects necesarios

#### FlashPointManager (GameObject vacío)
- Agregar script `FlashPointManager.cs`
- Configurar la URL del servidor: `http://localhost:3690`

#### UI Canvas
- Crear Canvas UI
- Agregar script `FlashPointUIController.cs`

#### Prefabs necesarios

**FirefighterPrefab:**
```
- Firefighter (GameObject)
  - Model: Cube o modelo 3D
  - Material: Material azul/rojo según role
  - Script: FirefighterController
  - Collider: Box Collider
```

**POIPrefab:**
```
- POI (GameObject)
  - Model: Sphere (pequeña)
  - Material: Material amarillo/naranja
  - Collider: Sphere Collider
```

**CellPrefab:**
```
- Cell (GameObject)
  - Model: Plane o Quad
  - Material: Material configurable por estado
  - Collider: Box Collider
```

### 3. Materiales necesarios

Crear los siguientes materiales en la carpeta Materials:

- **ClearCellMaterial**: Color blanco/gris claro
- **SmokeCellMaterial**: Color gris
- **FireCellMaterial**: Color rojo
- **ExitCellMaterial**: Color verde

### 4. UI Layout

#### Panel Principal (Canvas)
```
Canvas
├── GameInfoPanel
│   ├── CurrentStepText (TextMeshPro)
│   ├── RescuedPoisText (TextMeshPro)
│   ├── FireCellsText (TextMeshPro)
│   ├── SmokeCellsText (TextMeshPro)
│   └── ExplosionCountText (TextMeshPro)
├── ControlPanel
│   ├── CreateGameButton (Button)
│   ├── ExecuteStepButton (Button)
│   ├── ExecuteMultipleStepsButton (Button)
│   ├── StepsInputField (TMP_InputField)
│   ├── ResetGameButton (Button)
│   └── ConnectionStatusText (TextMeshPro)
├── FirefighterPanel
│   ├── ScrollView
│   └── FirefighterListParent (Transform)
├── POIPanel
│   ├── ScrollView
│   └── POIListParent (Transform)
├── CameraControlPanel
│   ├── ZoomInButton (Button)
│   ├── ZoomOutButton (Button)
│   └── ResetCameraButton (Button)
└── AutoModePanel
    ├── AutoModeToggle (Toggle)
    ├── AutoSpeedSlider (Slider)
    └── AutoSpeedText (TextMeshPro)
```

#### Prefabs UI

**FirefighterUIItemPrefab:**
```
FirefighterUIItem (Button)
├── FirefighterID (TextMeshPro)
├── Position (TextMeshPro)
├── ActionPoints (TextMeshPro)
├── Role (TextMeshPro)
└── CarryingPOI (TextMeshPro)
```

**POIUIItemPrefab:**
```
POIUIItem (GameObject)
├── POIID (TextMeshPro)
├── Position (TextMeshPro)
└── Status (TextMeshPro)
```

### 5. Configuración de la Cámara

Configurar la cámara principal:
- Position: (5, 8, 5)
- Rotation: (45, 0, 0)
- Projection: Perspective
- Field of View: 60

### 6. Scripts a crear

Los siguientes scripts deben estar en tu carpeta Scripts:

1. `FlashPointManager.cs` - Controlador principal
2. `FlashPointUIController.cs` - Controlador de UI
3. `FirefighterController.cs` - Controlador de bombero individual

### 7. Configuración del servidor Python

1. Instala las dependencias:
```bash
pip install -r requirements.txt
```

2. Asegúrate de que tu modelo Flash Point esté en el mismo directorio
3. Actualiza la importación en la API:
```python
from your_flashpoint_model import FlashPointModel, FirefighterAgent, FireState, CellType, POI
```

### 8. Ejecución

1. **Ejecutar servidor Python:**
```bash
python flashpoint_api.py
```

2. **Ejecutar Unity:**
   - Presiona Play
   - Haz clic en "Create Game"
   - Usa los controles para interactuar con la simulación

### 9. Troubleshooting

**Error de conexión:**
- Verificar que el servidor Python esté corriendo en el puerto 3690
- Verificar que no haya firewall bloqueando la conexión
- Verificar la URL en FlashPointManager

**Error de JSON:**
- Verificar que las clases de datos en Unity coincidan con la respuesta de la API
- Usar Debug.Log para ver el JSON crudo de respuesta

**Error de prefabs:**
- Verificar que todos los prefabs estén asignados en FlashPointManager
- Verificar que los prefabs tengan los componentes necesarios

### 10. Extensiones posibles

- **Control manual de bomberos:** Click para seleccionar y mover
- **Visualización de pathfinding:** Mostrar rutas planificadas
- **Efectos visuales:** Partículas para fuego y humo
- **Sonidos:** Efectos de sonido para acciones
- **Persistencia:** Guardar y cargar estados de juego