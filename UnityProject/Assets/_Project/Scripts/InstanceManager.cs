using UnityEngine;

public class InstanceManager : MonoBehaviour
{
    // Static instance accessible from anywhere
    public static InstanceManager Instance { get; private set; }
    public MediapipeUDP mediapipeUDP;
    public AvatarController avatarController;

    void Awake()
    {
        // If an instance already exists and it's not this, destroy this object
        if (Instance != null && Instance != this)
        {
            Destroy(gameObject);
            return;
        }

        // Assign this as the singleton instance
        Instance = this;

        // DontDestroyOnLoad(gameObject);
    }
}