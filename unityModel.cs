using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Networking;
using System;

[System.Serializable]
public class GameState
{
    public int step;
    public Dimensions dimensions;
    public List<FirefighterData> firefighters;
    public List<POIData> pois;
    public List<List<CellData>> fire_grid;
    public GameStats stats;
}

[System.Serializable]
public class Dimensions
{
    public int width;
    public int height;
}

[System.Serializable]
public class FirefighterData
{
    public int id;
    public Position position;
    public int action_points;
    public string role;
    public int? carrying_poi;
}

[System.Serializable]
public class POIData
{
    public int id;
    public Position position;
    public bool is_revealed;
    public bool is_rescued;
    public int? carried_by;
}

[System.Serializable]
public class CellData
{
    public string fire_state;
    public bool is_exit;
}

[System.Serializable]
public class Position
{
    public int x;
    public int y;
}

[System.Serializable]
public class GameStats
{
    public int rescued_pois;
    public int fire_cells;
    public int smoke_cells;
    public int explosion_count;
}

[System.Serializable]
public class APIResponse<T>
{
    public string status;
    public string message;
    public T state;
    public T data;
}

[System.Serializable]
public class CreateGameRequest
{
    public int width = 10;
    public int height = 8;
    public int num_firefighters = 5;
    public int initial_pois = 6;
}

public class FlashPointManager : MonoBehaviour
{
    [Header("API Configuration")]
    // Paoooo Aqui cambias por la dir que te de en tu compu
    public string serverURL = "http://localhost:3690";
    
    [Header("Game Objects")]
    public GameObject firefighterPrefab;
    public GameObject poiPrefab;
    public GameObject cellPrefab;
    public GameObject wallPrefab;
    
    [Header("Materials")]
    public Material clearCellMaterial;
    public Material smokeCellMaterial;
    public Material fireCellMaterial;
    public Material exitCellMaterial;
    
    // Game state
    private GameState currentGameState;
    private Dictionary<int, GameObject> firefighterObjects = new Dictionary<int, GameObject>();
    private Dictionary<int, GameObject> poiObjects = new Dictionary<int, GameObject>();
    private GameObject[,] cellObjects;
    
    // Events
    public System.Action<GameState> OnGameStateUpdated;
    public System.Action<string> OnAPIError;
    
    void Start()
    {
        StartCoroutine(TestConnection());
    }
    
    private IEnumerator TestConnection()
    {
        yield return StartCoroutine(MakeRequest<object>("GET", "/api/test", null, (response) => {
            Debug.Log("Successfully connected to Flash Point API");
        }));
    }
    
    public void CreateNewGame()
    {
        CreateGameRequest request = new CreateGameRequest();
        
        StartCoroutine(MakeRequest<GameState>("POST", "/api/game/create", request, (response) => {
            Debug.Log("Game created successfully!");
            currentGameState = response.state;
            InitializeGameScene();
            OnGameStateUpdated?.Invoke(currentGameState);
        }));
    }
    
    public void ExecuteStep()
    {
        StartCoroutine(MakeRequest<GameState>("POST", "/api/game/step", null, (response) => {
            Debug.Log($"Step executed: {response.message}");
            currentGameState = response.state;
            UpdateGameScene();
            OnGameStateUpdated?.Invoke(currentGameState);
        }));
    }
    
    public void ExecuteMultipleSteps(int numSteps)
    {
        StartCoroutine(MakeRequest<GameState>("POST", $"/api/game/steps/{numSteps}", null, (response) => {
            Debug.Log($"Multiple steps executed: {response.message}");
            currentGameState = response.state;
            UpdateGameScene();
            OnGameStateUpdated?.Invoke(currentGameState);
        }));
    }
    
    public void MoveFirefighter(int firefighterId, int targetX, int targetY)
    {
        var moveRequest = new { x = targetX, y = targetY };
        
        StartCoroutine(MakeRequest<object>("POST", $"/api/firefighter/{firefighterId}/move", moveRequest, (response) => {
            Debug.Log($"Firefighter {firefighterId} move result: {response.message}");
            RefreshGameState();
        }));
    }
    
    public void ExtinguishFire(int firefighterId)
    {
        StartCoroutine(MakeRequest<object>("POST", $"/api/firefighter/{firefighterId}/extinguish", null, (response) => {
            Debug.Log($"Extinguish result: {response.message}");
            RefreshGameState();
        }));
    }
    
    public void RefreshGameState()
    {
        StartCoroutine(MakeRequest<GameState>("GET", "/api/game/state", null, (response) => {
            currentGameState = response.state;
            UpdateGameScene();
            OnGameStateUpdated?.Invoke(currentGameState);
        }));
    }
    
    private void InitializeGameScene()
    {
        if (currentGameState == null) return;
        
        // Clear existing objects
        ClearScene();
        
        // Initialize cell grid
        InitializeCells();
        
        // Create firefighters
        CreateFirefighters();
        
        // Create POIs
        CreatePOIs();
        
        // Update visual state
        UpdateGameScene();
    }
    
    private void InitializeCells()
    {
        if (currentGameState?.dimensions == null) return;
        
        int width = currentGameState.dimensions.width;
        int height = currentGameState.dimensions.height;
        
        cellObjects = new GameObject[width, height];
        
        for (int x = 0; x < width; x++)
        {
            for (int y = 0; y < height; y++)
            {
                Vector3 position = new Vector3(x, 0, y);
                GameObject cell = Instantiate(cellPrefab, position, Quaternion.identity, transform);
                cell.name = $"Cell_{x}_{y}";
                cellObjects[x, y] = cell;
            }
        }
    }
    
    private void CreateFirefighters()
    {
        if (currentGameState?.firefighters == null) return;
        
        foreach (var firefighter in currentGameState.firefighters)
        {
            Vector3 position = new Vector3(firefighter.position.x, 0.5f, firefighter.position.y);
            GameObject ff = Instantiate(firefighterPrefab, position, Quaternion.identity, transform);
            ff.name = $"Firefighter_{firefighter.id}";
            
            // Add firefighter component if needed
            var ffComponent = ff.GetComponent<FirefighterController>() ?? ff.AddComponent<FirefighterController>();
            ffComponent.Initialize(firefighter.id, this);
            
            firefighterObjects[firefighter.id] = ff;
        }
    }
    
    private void CreatePOIs()
    {
        if (currentGameState?.pois == null) return;
        
        foreach (var poi in currentGameState.pois)
        {
            if (!poi.is_rescued && poi.carried_by == null)
            {
                Vector3 position = new Vector3(poi.position.x, 0.2f, poi.position.y);
                GameObject poiObj = Instantiate(poiPrefab, position, Quaternion.identity, transform);
                poiObj.name = $"POI_{poi.id}";
                poiObjects[poi.id] = poiObj;
            }
        }
    }
    
    private void UpdateGameScene()
    {
        if (currentGameState == null) return;
        
        // Update cells
        UpdateCells();
        
        // Update firefighters
        UpdateFirefighters();
        
        // Update POIs
        UpdatePOIs();
    }
    
    private void UpdateCells()
    {
        if (currentGameState?.fire_grid == null || cellObjects == null) return;
        
        for (int y = 0; y < currentGameState.fire_grid.Count; y++)
        {
            for (int x = 0; x < currentGameState.fire_grid[y].Count; x++)
            {
                if (x < cellObjects.GetLength(0) && y < cellObjects.GetLength(1))
                {
                    var cellData = currentGameState.fire_grid[y][x];
                    var cellObject = cellObjects[x, y];
                    
                    if (cellObject != null)
                    {
                        var renderer = cellObject.GetComponent<Renderer>();
                        if (renderer != null)
                        {
                            Material material = GetCellMaterial(cellData);
                            renderer.material = material;
                        }
                    }
                }
            }
        }
    }
    
    private Material GetCellMaterial(CellData cellData)
    {
        if (cellData.is_exit)
            return exitCellMaterial;
        
        switch (cellData.fire_state)
        {
            case "FIRE":
                return fireCellMaterial;
            case "SMOKE":
                return smokeCellMaterial;
            case "CLEAR":
            default:
                return clearCellMaterial;
        }
    }
    
    private void UpdateFirefighters()
    {
        if (currentGameState?.firefighters == null) return;
        
        foreach (var firefighter in currentGameState.firefighters)
        {
            if (firefighterObjects.ContainsKey(firefighter.id))
            {
                var ffObject = firefighterObjects[firefighter.id];
                Vector3 targetPosition = new Vector3(firefighter.position.x, 0.5f, firefighter.position.y);
                
                // Smooth movement
                StartCoroutine(MoveObjectSmoothly(ffObject, targetPosition, 0.5f));
                
                // Update firefighter component
                var ffComponent = ffObject.GetComponent<FirefighterController>();
                if (ffComponent != null)
                {
                    ffComponent.UpdateData(firefighter);
                }
            }
        }
    }
    
    private void UpdatePOIs()
    {
        if (currentGameState?.pois == null) return;
        
        // Remove rescued or carried POIs
        List<int> toRemove = new List<int>();
        foreach (var kvp in poiObjects)
        {
            var poi = currentGameState.pois.Find(p => p.id == kvp.Key);
            if (poi == null || poi.is_rescued || poi.carried_by != null)
            {
                Destroy(kvp.Value);
                toRemove.Add(kvp.Key);
            }
        }
        
        foreach (int id in toRemove)
        {
            poiObjects.Remove(id);
        }
        
        // Add new POIs if any
        foreach (var poi in currentGameState.pois)
        {
            if (!poi.is_rescued && poi.carried_by == null && !poiObjects.ContainsKey(poi.id))
            {
                Vector3 position = new Vector3(poi.position.x, 0.2f, poi.position.y);
                GameObject poiObj = Instantiate(poiPrefab, position, Quaternion.identity, transform);
                poiObj.name = $"POI_{poi.id}";
                poiObjects[poi.id] = poiObj;
            }
        }
    }
    
    private IEnumerator MoveObjectSmoothly(GameObject obj, Vector3 targetPosition, float duration)
    {
        Vector3 startPosition = obj.transform.position;
        float elapsed = 0;
        
        while (elapsed < duration)
        {
            elapsed += Time.deltaTime;
            float t = elapsed / duration;
            obj.transform.position = Vector3.Lerp(startPosition, targetPosition, t);
            yield return null;
        }
        
        obj.transform.position = targetPosition;
    }
    
    private void ClearScene()
    {
        // Clear firefighters
        foreach (var ff in firefighterObjects.Values)
        {
            if (ff != null) Destroy(ff);
        }
        firefighterObjects.Clear();
        
        // Clear POIs
        foreach (var poi in poiObjects.Values)
        {
            if (poi != null) Destroy(poi);
        }
        poiObjects.Clear();
        
        // Clear cells
        if (cellObjects != null)
        {
            for (int x = 0; x < cellObjects.GetLength(0); x++)
            {
                for (int y = 0; y < cellObjects.GetLength(1); y++)
                {
                    if (cellObjects[x, y] != null)
                        Destroy(cellObjects[x, y]);
                }
            }
            cellObjects = null;
        }
    }
    
    private IEnumerator MakeRequest<T>(string method, string endpoint, object data, System.Action<APIResponse<T>> onSuccess)
    {
        string url = serverURL + endpoint;
        UnityWebRequest request;
        
        if (method == "GET")
        {
            request = UnityWebRequest.Get(url);
        }
        else
        {
            request = new UnityWebRequest(url, method);
            
            if (data != null)
            {
                string jsonData = JsonUtility.ToJson(data);
                byte[] bodyRaw = System.Text.Encoding.UTF8.GetBytes(jsonData);
                request.uploadHandler = new UploadHandlerRaw(bodyRaw);
            }
            
            request.downloadHandler = new DownloadHandlerBuffer();
            request.SetRequestHeader("Content-Type", "application/json");
        }
        
        yield return request.SendWebRequest();
        
        if (request.result == UnityWebRequest.Result.Success)
        {
            try
            {
                string responseText = request.downloadHandler.text;
                APIResponse<T> response = JsonUtility.FromJson<APIResponse<T>>(responseText);
                onSuccess?.Invoke(response);
            }
            catch (System.Exception e)
            {
                Debug.LogError($"Failed to parse response: {e.Message}");
                OnAPIError?.Invoke($"Failed to parse response: {e.Message}");
            }
        }
        else
        {
            Debug.LogError($"API request failed: {request.error}");
            OnAPIError?.Invoke($"API request failed: {request.error}");
        }
        
        request.Dispose();
    }
    
    public void ResetGame()
    {
        StartCoroutine(MakeRequest<object>("POST", "/api/game/reset", null, (response) => {
            Debug.Log("Game reset");
            ClearScene();
            currentGameState = null;
        }));
    }
}

// Component para controlar bomberos individuales
public class FirefighterController : MonoBehaviour
{
    public int firefighterId;
    public FirefighterData data;
    private FlashPointManager manager;
    
    public void Initialize(int id, FlashPointManager mgr)
    {
        firefighterId = id;
        manager = mgr;
    }
    
    public void UpdateData(FirefighterData newData)
    {
        data = newData;
        
        // Update visual representation based on role, AP, etc.
        UpdateVisuals();
    }
    
    private void UpdateVisuals()
    {
        // Change color based on role
        var renderer = GetComponent<Renderer>();
        if (renderer != null)
        {
            if (data.role == "rescuer")
                renderer.material.color = Color.blue;
            else
                renderer.material.color = Color.red;
        }
        
        // Show AP indicator or other visual feedback
    }
    
    public void MoveTo(int x, int y)
    {
        manager.MoveFirefighter(firefighterId, x, y);
    }
    
    public void ExtinguishFire()
    {
        manager.ExtinguishFire(firefighterId);
    }
}