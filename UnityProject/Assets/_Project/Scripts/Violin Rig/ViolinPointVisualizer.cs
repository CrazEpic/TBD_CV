using UnityEngine;
using System.Collections.Generic;

public class ViolinPointVisualizer : MonoBehaviour
{
    // Dictionary to store violin point game objects
    private Dictionary<string, GameObject> violinPointsDict = new Dictionary<string, GameObject>();
    
    // Prefab for violin points (red spheres)
    public GameObject violinPointPrefab;
    
    // Reference to MediapipeUDP for accessing violin point data
    private MediapipeUDP mediapipeUDP;
    
    // Offset for positioning
    public Vector3 violinPointsOffset = Vector3.zero;
    
    void Start()
    {
        mediapipeUDP = InstanceManager.Instance.mediapipeUDP;
        
        if (mediapipeUDP == null)
        {
            Debug.LogError("ViolinPointVisualizer: Cannot find MediapipeUDP in InstanceManager!");
            return;
        }
        
        Debug.Log("ViolinPointVisualizer: Initialized with MediapipeUDP");
        
        // Ensure we have a prefab, otherwise create a simple sphere
        if (violinPointPrefab == null)
        {
            violinPointPrefab = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            violinPointPrefab.name = "ViolinPointPrefab";
            
            // Remove the collider from the prefab to save performance
            Collider collider = violinPointPrefab.GetComponent<Collider>();
            if (collider != null)
            {
                DestroyImmediate(collider);
            }
            
            // Set up red material
            MeshRenderer renderer = violinPointPrefab.GetComponent<MeshRenderer>();
            if (renderer != null)
            {
                Material redMat = new Material(Shader.Find("Standard"));
                redMat.color = new Color(1.0f, 0.0f, 0.0f, 0.7f); // Red
                renderer.material = redMat;
            }
            
            violinPointPrefab.transform.localScale = new Vector3(0.04f, 0.04f, 0.04f); // Small sphere (doubled)
            violinPointPrefab.SetActive(false);
            
            Debug.Log("ViolinPointVisualizer: Created red sphere prefab");
        }
    }
    
    void Update()
    {
        if (mediapipeUDP == null)
        {
            Debug.LogWarning("ViolinPointVisualizer: MediapipeUDP is null!");
            return;
        }
        
        lock (mediapipeUDP.lockObject)
        {
            if (!mediapipeUDP.hybridStateValid)
            {
                if (Time.frameCount % 60 == 0)  // Log every 60 frames to avoid spam
                    Debug.LogWarning("ViolinPointVisualizer: hybridStateValid is false - no data being received");
                return;
            }
            
            // Debug: Print all joint keys that start with "violin_"
            int violinCount = 0;
            foreach (var kv in mediapipeUDP.hybridJointPositions)
            {
                if (kv.Key.StartsWith("violin_", System.StringComparison.Ordinal))
                {
                    violinCount++;
                }
            }
            
            if (violinCount > 0)
                Debug.Log($"ViolinPointVisualizer: Found {violinCount} violin joints in hybridJointPositions");
            
            // Get all violin points from hybrid joint positions
            List<string> violinPointKeys = new List<string>();
            foreach (var kv in mediapipeUDP.hybridJointPositions)
            {
                if (kv.Key.StartsWith("violin_", System.StringComparison.Ordinal))
                {
                    violinPointKeys.Add(kv.Key);
                }
            }
            
            if (violinPointKeys.Count > 0 && violinPointsDict.Count == 0)
            {
                Debug.Log($"ViolinPointVisualizer: Found {violinPointKeys.Count} violin points!");
            }
            
            // Update existing points and create new ones as needed
            foreach (string pointKey in violinPointKeys)
            {
                Vector3 pos = mediapipeUDP.hybridJointPositions[pointKey];
                float confidence = mediapipeUDP.hybridJointConfidences.ContainsKey(pointKey) ? 
                    mediapipeUDP.hybridJointConfidences[pointKey] : 0.5f;
                
                // Create or update the game object
                if (!violinPointsDict.ContainsKey(pointKey))
                {
                    GameObject pointObj = Instantiate(violinPointPrefab);
                    pointObj.name = pointKey;
                    pointObj.SetActive(true);
                    violinPointsDict[pointKey] = pointObj;
                    Debug.Log($"ViolinPointVisualizer: Created point {pointKey}");
                }
                
                GameObject go = violinPointsDict[pointKey];
                go.transform.position = pos + violinPointsOffset;
                
                // Scale based on confidence
                float scale = Mathf.Lerp(0.02f, 0.06f, confidence);
                go.transform.localScale = new Vector3(scale, scale, scale);
            }
            
            // Remove points that no longer exist in the data
            List<string> keysToRemove = new List<string>();
            foreach (var kv in violinPointsDict)
            {
                if (!violinPointKeys.Contains(kv.Key))
                {
                    keysToRemove.Add(kv.Key);
                }
            }
            
            foreach (string key in keysToRemove)
            {
                Destroy(violinPointsDict[key]);
                violinPointsDict.Remove(key);
            }
        }
    }
    
    void OnDestroy()
    {
        // Clean up
        foreach (var go in violinPointsDict.Values)
        {
            if (go != null)
                Destroy(go);
        }
        violinPointsDict.Clear();
    }
}
