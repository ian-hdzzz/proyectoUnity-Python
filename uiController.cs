using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using TMPro;

public class FlashPointUIController : MonoBehaviour
{
    [Header("UI References")]
    public Button createGameButton;
    public Button executeStepButton;
    public Button executeMultipleStepsButton;
    public Button resetGameButton;
    public TMP_InputField stepsInputField;
    
    [Header("Game Info Display")]
    public TextMeshProUGUI currentStepText;
    public TextMeshProUGUI rescuedPoisText;
    public TextMeshProUGUI fireCellsText;
    public TextMeshProUGUI smokeCellsText;
    public TextMeshProUGUI explosionCountText;
    public TextMeshProUGUI connectionStatusText;
    
    [Header("Firefighter Panel")]
    public Transform firefighterListParent;
    public GameObject firefighterUIItemPrefab;
    
    [Header("POI Panel")]
    public Transform poiListParent;
    public GameObject poiUIItemPrefab;
    
    [Header("Camera Controls")]
    public Button zoomInButton;
    public Button zoomOutButton;
    public Button resetCameraButton;
    public Camera mainCamera;
    
    [Header("Game Control Panel")]
    public Toggle autoModeToggle;
    public Slider autoSpeedSlider;
    public TextMeshProUGUI autoSpeedText;
    
    private FlashPointManager gameManager;
    private bool isAutoMode = false;
    private float autoStepInterval = 2.0f;
    private Coroutine autoModeCoroutine;
    
    // UI Item tracking
    private Dictionary<int, GameObject> firefighterUIItems = new Dictionary<int, GameObject>();
    private Dictionary<int, GameObject> poiUIItems = new Dictionary<int, GameObject>();
    
    void Start()
    {
        gameManager = FindObjectOfType<FlashPointManager>();
        
        if (gameManager == null)
        {
            Debug.LogError("FlashPointManager not found!");
            return;
        }
        
        SetupUI();
        SetupEventListeners();
    }
    
    private void SetupUI()
    {
        // Initialize UI state
        UpdateConnectionStatus("Connecting...");
        
        // Set default values
        stepsInputField.text = "5";
        autoSpeedSlider.value = 2.0f;
        UpdateAutoSpeedText(2.0f);
        
        // Initially disable game controls
        SetGameControlsEnabled(false);
    }
    
    private void SetupEventListeners()
    {
        // Button events
        createGameButton.onClick.AddListener(OnCreateGame);
        executeStepButton.onClick.AddListener(OnExecuteStep);
        executeMultipleStepsButton.onClick.AddListener(OnExecuteMultipleSteps);
        resetGameButton.onClick.AddListener(OnResetGame);
        
        // Camera controls
        zoomInButton.onClick.AddListener(OnZoomIn);
        zoomOutButton.onClick.AddListener(OnZoomOut);
        resetCameraButton.onClick.AddListener(OnResetCamera);
        
        // Auto mode controls
        autoModeToggle.onValueChanged.AddListener(OnAutoModeToggle);
        autoSpeedSlider.onValueChanged.AddListener(OnAutoSpeedChanged);
        
        // Game manager events
        gameManager.OnGameStateUpdated += OnGameStateUpdated;
        gameManager.OnAPIError += OnAPIError;
    }
    
    private void OnCreateGame()
    {
        createGameButton.interactable = false;
        UpdateConnectionStatus("Creating game...");
        gameManager.CreateNewGame();
    }
    
    private void OnExecuteStep()
    {
        executeStepButton.interactable = false;
        gameManager.ExecuteStep();
        StartCoroutine(ReenableButtonAfterDelay(executeStepButton, 1.0f));
    }
    
    private void OnExecuteMultipleSteps()
    {
        if (int.TryParse(stepsInputField.text, out int steps) && steps > 0)
        {
            executeMultipleStepsButton.interactable = false;
            gameManager.ExecuteMultipleSteps(steps);
            StartCoroutine(ReenableButtonAfterDelay(executeMultipleStepsButton, steps * 0.5f));
        }
    }
    
    private void OnResetGame()
    {
        if (autoModeCoroutine != null)
        {
            StopCoroutine(autoModeCoroutine);
            autoModeCoroutine = null;
        }
        
        autoModeToggle.isOn = false;
        gameManager.ResetGame();
        ClearFirefighterUI();
        ClearPOIUI();
        SetGameControlsEnabled(false);
        UpdateConnectionStatus("Game reset");
    }
    
    private void OnAutoModeToggle(bool isOn)
    {
        isAutoMode = isOn;
        
        if (isAutoMode)
        {
            // Start auto mode
            if (autoModeCoroutine != null)
                StopCoroutine(autoModeCoroutine);
            autoModeCoroutine = StartCoroutine(AutoModeCoroutine());
            
            // Disable manual controls
            executeStepButton.interactable = false;
            executeMultipleStepsButton.interactable = false;
        }
        else
        {
            // Stop auto mode
            if (autoModeCoroutine != null)
            {
                StopCoroutine(autoModeCoroutine);
                autoModeCoroutine = null;
            }
            
            // Re-enable manual controls
            executeStepButton.interactable = true;
            executeMultipleStepsButton.interactable = true;
        }
    }
    
    private void OnAutoSpeedChanged(float value)
    {
        autoStepInterval = value;
        UpdateAutoSpeedText(value);
    }
    
    private void UpdateAutoSpeedText(float value)
    {
        autoSpeedText.text = $"Auto Speed: {value:F1}s";
    }
    
    private IEnumerator AutoModeCoroutine()
    {
        while (isAutoMode)
        {
            yield return new WaitForSeconds(autoStepInterval);
            gameManager.ExecuteStep();
        }
    }
    
    private void OnGameStateUpdated(GameState gameState)
    {
        UpdateGameInfoDisplay(gameState);
        UpdateFirefighterUI(gameState.firefighters);
        UpdatePOIUI(gameState.pois);
        SetGameControlsEnabled(true);
        UpdateConnectionStatus("Connected");
        
        // Re-enable create game button
        createGameButton.interactable = true;
    }
    
    private void OnAPIError(string error)
    {
        UpdateConnectionStatus($"Error: {error}");
        Debug.LogError($"API Error: {error}");
        
        // Re-enable buttons
        createGameButton.interactable = true;
        executeStepButton.interactable = true;
        executeMultipleStepsButton.interactable = true;
    }
    
    private void UpdateGameInfoDisplay(GameState gameState)
    {
        if (gameState?.stats == null) return;
        
        currentStepText.text = $"Step: {gameState.step}";
        rescuedPoisText.text = $"Rescued POIs: {gameState.stats.rescued_pois}";
        fireCellsText.text = $"Fire Cells: {gameState.stats.fire_cells}";
        smokeCellsText.text = $"Smoke Cells: {gameState.stats.smoke_cells}";
        explosionCountText.text = $"Explosions: {gameState.stats.explosion_count}";
    }
    
    private void UpdateFirefighterUI(List<FirefighterData> firefighters)
    {
        if (firefighters == null) return;
        
        // Remove UI items for firefighters that no longer exist
        List<int> toRemove = new List<int>();
        foreach (var kvp in firefighterUIItems)
        {
            if (firefighters.Find(f => f.id == kvp.Key) == null)
            {
                Destroy(kvp.Value);
                toRemove.Add(kvp.Key);
            }
        }
        foreach (int id in toRemove)
        {
            firefighterUIItems.Remove(id);
        }
        
        // Update or create UI items for current firefighters
        foreach (var firefighter in firefighters)
        {
            if (firefighterUIItems.ContainsKey(firefighter.id))
            {
                UpdateFirefighterUIItem(firefighterUIItems[firefighter.id], firefighter);
            }
            else
            {
                GameObject uiItem = CreateFirefighterUIItem(firefighter);
                firefighterUIItems[firefighter.id] = uiItem;
            }
        }
    }
    
    private GameObject CreateFirefighterUIItem(FirefighterData firefighter)
    {
        GameObject uiItem = Instantiate(firefighterUIItemPrefab, firefighterListParent);
        UpdateFirefighterUIItem(uiItem, firefighter);
        
        // Add click handler for firefighter selection
        Button button = uiItem.GetComponent<Button>();
        if (button != null)
        {
            int ffId = firefighter.id; // Capture for closure
            button.onClick.AddListener(() => OnFirefighterSelected(ffId));
        }
        
        return uiItem;
    }
    
    private void UpdateFirefighterUIItem(GameObject uiItem, FirefighterData firefighter)
    {
        // Update firefighter info display
        TextMeshProUGUI[] texts = uiItem.GetComponentsInChildren<TextMeshProUGUI>();
        
        foreach (var text in texts)
        {
            switch (text.name)
            {
                case "FirefighterID":
                    text.text = $"FF {firefighter.id}";
                    break;
                case "Position":
                    text.text = $"({firefighter.position.x}, {firefighter.position.y})";
                    break;
                case "ActionPoints":
                    text.text = $"AP: {firefighter.action_points}";
                    break;
                case "Role":
                    text.text = firefighter.role;
                    text.color = firefighter.role == "rescuer" ? Color.blue : Color.red;
                    break;
                case "CarryingPOI":
                    text.text = firefighter.carrying_poi.HasValue ? $"Carrying POI {firefighter.carrying_poi}" : "";
                    break;
            }
        }
    }
    
    private void UpdatePOIUI(List<POIData> pois)
    {
        if (pois == null) return;
        
        // Remove UI items for POIs that no longer exist or are rescued
        List<int> toRemove = new List<int>();
        foreach (var kvp in poiUIItems)
        {
            var poi = pois.Find(p => p.id == kvp.Key);
            if (poi == null || poi.is_rescued)
            {
                Destroy(kvp.Value);
                toRemove.Add(kvp.Key);
            }
        }
        foreach (int id in toRemove)
        {
            poiUIItems.Remove(id);
        }
        
        // Update or create UI items for active POIs
        foreach (var poi in pois)
        {
            if (!poi.is_rescued)
            {
                if (poiUIItems.ContainsKey(poi.id))
                {
                    UpdatePOIUIItem(poiUIItems[poi.id], poi);
                }
                else
                {
                    GameObject uiItem = CreatePOIUIItem(poi);
                    poiUIItems[poi.id] = uiItem;
                }
            }
        }
    }
    
    private GameObject CreatePOIUIItem(POIData poi)
    {
        GameObject uiItem = Instantiate(poiUIItemPrefab, poiListParent);
        UpdatePOIUIItem(uiItem, poi);
        return uiItem;
    }
    
    private void UpdatePOIUIItem(GameObject uiItem, POIData poi)
    {
        TextMeshProUGUI[] texts = uiItem.GetComponentsInChildren<TextMeshProUGUI>();
        
        foreach (var text in texts)
        {
            switch (text.name)
            {
                case "POIID":
                    text.text = $"POI {poi.id}";
                    break;
                case "Position":
                    text.text = $"({poi.position.x}, {poi.position.y})";
                    break;
                case "Status":
                    if (poi.carried_by.HasValue)
                        text.text = $"Carried by FF {poi.carried_by}";
                    else if (poi.is_revealed)
                        text.text = "Revealed";
                    else
                        text.text = "Hidden";
                    break;
            }
        }
    }
    
    private void OnFirefighterSelected(int firefighterId)
    {
        // Highlight selected firefighter or show detailed info
        Debug.Log($"Firefighter {firefighterId} selected");
        
        // You could implement firefighter-specific actions here
        // For example, show a panel with move/extinguish buttons
    }
    
    private void ClearFirefighterUI()
    {
        foreach (var uiItem in firefighterUIItems.Values)
        {
            if (uiItem != null) Destroy(uiItem);
        }
        firefighterUIItems.Clear();
    }
    
    private void ClearPOIUI()
    {
        foreach (var uiItem in poiUIItems.Values)
        {
            if (uiItem != null) Destroy(uiItem);
        }
        poiUIItems.Clear();
    }
    
    private void SetGameControlsEnabled(bool enabled)
    {
        executeStepButton.interactable = enabled && !isAutoMode;
        executeMultipleStepsButton.interactable = enabled && !isAutoMode;
        resetGameButton.interactable = enabled;
        autoModeToggle.interactable = enabled;
    }
    
    private void UpdateConnectionStatus(string status)
    {
        connectionStatusText.text = $"Status: {status}";
        
        // Color coding for status
        if (status.Contains("Error"))
            connectionStatusText.color = Color.red;
        else if (status.Contains("Connected"))
            connectionStatusText.color = Color.green;
        else
            connectionStatusText.color = Color.yellow;
    }
    
    private IEnumerator ReenableButtonAfterDelay(Button button, float delay)
    {
        yield return new WaitForSeconds(delay);
        button.interactable = true;
    }
    
    // Camera control methods
    private void OnZoomIn()
    {
        if (mainCamera != null)
        {
            mainCamera.fieldOfView = Mathf.Max(20f, mainCamera.fieldOfView - 10f);
        }
    }
    
    private void OnZoomOut()
    {
        if (mainCamera != null)
        {
            mainCamera.fieldOfView = Mathf.Min(80f, mainCamera.fieldOfView + 10f);
        }
    }
    
    private void OnResetCamera()
    {
        if (mainCamera != null)
        {
            mainCamera.transform.position = new Vector3(5, 8, 5);
            mainCamera.transform.rotation = Quaternion.Euler(45, 0, 0);
            mainCamera.fieldOfView = 60f;
        }
    }
    
    void OnDestroy()
    {
        // Clean up event listeners
        if (gameManager != null)
        {
            gameManager.OnGameStateUpdated -= OnGameStateUpdated;
            gameManager.OnAPIError -= OnAPIError;
        }
        
        if (autoModeCoroutine != null)
        {
            StopCoroutine(autoModeCoroutine);
        }
    }
}