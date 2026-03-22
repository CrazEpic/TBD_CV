using UnityEngine;
using System.Net;
using System.Net.Sockets;
using System.Threading;
using System.Collections.Generic;

public class MediapipeUDP : MonoBehaviour
{
    public int port = 5005;
    public int numJoints = 33;

    private UdpClient udpClient;
    private Thread receiveThread;
    private readonly object lockObject = new();

    // Typed enum for landmarks
    public enum Landmark
    {
        Nose = 0,
        LeftEyeInner = 1, LeftEye = 2, LeftEyeOuter = 3,
        RightEyeInner = 4, RightEye = 5, RightEyeOuter = 6,
        LeftEar = 7, RightEar = 8,
        MouthLeft = 9, MouthRight = 10,
        LeftShoulder = 11, RightShoulder = 12,
        LeftElbow = 13, RightElbow = 14,
        LeftWrist = 15, RightWrist = 16,
        LeftPinky = 17, RightPinky = 18,
        LeftIndex = 19, RightIndex = 20,
        LeftThumb = 21, RightThumb = 22,
        LeftHip = 23, RightHip = 24,
        LeftKnee = 25, RightKnee = 26,
        LeftAnkle = 27, RightAnkle = 28,
        LeftHeel = 29, RightHeel = 30,
        LeftFootIndex = 31, RightFootIndex = 32
    }

    // Dictionary-based landmarks and visibilities
    public Dictionary<Landmark, Vector3> landmarksDict;
    public Dictionary<Landmark, float> jointVisibilitiesDict;

    public GameObject jointPrefab;
    public Dictionary<Landmark, GameObject> jointObjectsDict;
    public Vector3 jointObjectsOffset = Vector3.zero;

    public bool flipX = false;
    public bool flipY = true;
    public bool flipZ = true;

    void Start()
    {
        jointObjectsDict = new Dictionary<Landmark, GameObject>();
        landmarksDict = new Dictionary<Landmark, Vector3>();
        jointVisibilitiesDict = new Dictionary<Landmark, float>();

        // Initialize dictionaries and GameObjects
        foreach (Landmark lm in System.Enum.GetValues(typeof(Landmark)))
        {
            landmarksDict[lm] = Vector3.zero;
            jointVisibilitiesDict[lm] = 0f;

            GameObject jointObj = Instantiate(jointPrefab);
            jointObj.name = "Joint_" + lm.ToString();
            jointObjectsDict[lm] = jointObj;
        }

        // Start UDP receiver
        udpClient = new UdpClient(port);
        receiveThread = new Thread(ReceiveData)
        {
            IsBackground = true
        };
        receiveThread.Start();
    }

    void ReceiveData()
    {
        IPEndPoint remoteEndPoint = new IPEndPoint(IPAddress.Any, port);
        while (true)
        {
            try
            {
                byte[] data = udpClient.Receive(ref remoteEndPoint);
                float[] floats = new float[data.Length / 4];
                for (int i = 0; i < floats.Length; i++)
                    floats[i] = System.BitConverter.ToSingle(data, i * 4);

                lock (lockObject)
                {
                    for (int i = 0; i < numJoints; i++)
                    {
                        float x = floats[i * 4 + 0];
                        float y = floats[i * 4 + 1];
                        float z = floats[i * 4 + 2];

                        if (flipX) x = -x;
                        if (flipY) y = -y;
                        if (flipZ) z = -z;

                        Landmark lm = (Landmark)i;
                        landmarksDict[lm] = new Vector3(x, y, z);
                        jointVisibilitiesDict[lm] = floats[i * 4 + 3];
                    }
                }
            }
            catch { }
        }
    }

    void Update()
    {
        lock (lockObject)
        {
            foreach (Landmark lm in System.Enum.GetValues(typeof(Landmark)))
            {
                GameObject jointObj = jointObjectsDict[lm];
                if (jointObj != null)
                {
                    jointObj.transform.position = landmarksDict[lm] + jointObjectsOffset;
                }
            }
        }

        DrawSkeleton();
    }

    void DrawSkeleton()
    {
        // Head / Face
        Debug.DrawLine(jointObjectsDict[Landmark.Nose].transform.position, jointObjectsDict[Landmark.LeftEyeInner].transform.position, Color.cyan);
        Debug.DrawLine(jointObjectsDict[Landmark.LeftEyeInner].transform.position, jointObjectsDict[Landmark.LeftEye].transform.position, Color.cyan);
        Debug.DrawLine(jointObjectsDict[Landmark.LeftEye].transform.position, jointObjectsDict[Landmark.LeftEyeOuter].transform.position, Color.cyan);

        Debug.DrawLine(jointObjectsDict[Landmark.Nose].transform.position, jointObjectsDict[Landmark.RightEyeInner].transform.position, Color.red);
        Debug.DrawLine(jointObjectsDict[Landmark.RightEyeInner].transform.position, jointObjectsDict[Landmark.RightEye].transform.position, Color.red);
        Debug.DrawLine(jointObjectsDict[Landmark.RightEye].transform.position, jointObjectsDict[Landmark.RightEyeOuter].transform.position, Color.red);

        Debug.DrawLine(jointObjectsDict[Landmark.Nose].transform.position, jointObjectsDict[Landmark.MouthLeft].transform.position, Color.cyan);
        Debug.DrawLine(jointObjectsDict[Landmark.Nose].transform.position, jointObjectsDict[Landmark.MouthRight].transform.position, Color.red);

        // Shoulders & Arms
        Debug.DrawLine(jointObjectsDict[Landmark.LeftShoulder].transform.position, jointObjectsDict[Landmark.LeftElbow].transform.position, Color.cyan);
        Debug.DrawLine(jointObjectsDict[Landmark.LeftElbow].transform.position, jointObjectsDict[Landmark.LeftWrist].transform.position, Color.cyan);

        Debug.DrawLine(jointObjectsDict[Landmark.RightShoulder].transform.position, jointObjectsDict[Landmark.RightElbow].transform.position, Color.red);
        Debug.DrawLine(jointObjectsDict[Landmark.RightElbow].transform.position, jointObjectsDict[Landmark.RightWrist].transform.position, Color.red);

        Debug.DrawLine(jointObjectsDict[Landmark.LeftShoulder].transform.position, jointObjectsDict[Landmark.RightShoulder].transform.position, Color.yellow);

        // Hands / Fingers
        Debug.DrawLine(jointObjectsDict[Landmark.LeftWrist].transform.position, jointObjectsDict[Landmark.LeftPinky].transform.position, Color.blue);
        Debug.DrawLine(jointObjectsDict[Landmark.LeftWrist].transform.position, jointObjectsDict[Landmark.LeftIndex].transform.position, Color.blue);
        Debug.DrawLine(jointObjectsDict[Landmark.LeftWrist].transform.position, jointObjectsDict[Landmark.LeftThumb].transform.position, Color.blue);

        Debug.DrawLine(jointObjectsDict[Landmark.RightWrist].transform.position, jointObjectsDict[Landmark.RightPinky].transform.position, Color.magenta);
        Debug.DrawLine(jointObjectsDict[Landmark.RightWrist].transform.position, jointObjectsDict[Landmark.RightIndex].transform.position, Color.magenta);
        Debug.DrawLine(jointObjectsDict[Landmark.RightWrist].transform.position, jointObjectsDict[Landmark.RightThumb].transform.position, Color.magenta);

        // Torso
        Debug.DrawLine(jointObjectsDict[Landmark.LeftShoulder].transform.position, jointObjectsDict[Landmark.LeftHip].transform.position, Color.cyan);
        Debug.DrawLine(jointObjectsDict[Landmark.RightShoulder].transform.position, jointObjectsDict[Landmark.RightHip].transform.position, Color.red);
        Debug.DrawLine(jointObjectsDict[Landmark.LeftHip].transform.position, jointObjectsDict[Landmark.RightHip].transform.position, Color.yellow);

        // Legs
        Debug.DrawLine(jointObjectsDict[Landmark.LeftHip].transform.position, jointObjectsDict[Landmark.LeftKnee].transform.position, Color.cyan);
        Debug.DrawLine(jointObjectsDict[Landmark.LeftKnee].transform.position, jointObjectsDict[Landmark.LeftAnkle].transform.position, Color.cyan);

        Debug.DrawLine(jointObjectsDict[Landmark.RightHip].transform.position, jointObjectsDict[Landmark.RightKnee].transform.position, Color.red);
        Debug.DrawLine(jointObjectsDict[Landmark.RightKnee].transform.position, jointObjectsDict[Landmark.RightAnkle].transform.position, Color.red);

        // Feet
        Debug.DrawLine(jointObjectsDict[Landmark.LeftAnkle].transform.position, jointObjectsDict[Landmark.LeftHeel].transform.position, Color.cyan);
        Debug.DrawLine(jointObjectsDict[Landmark.LeftAnkle].transform.position, jointObjectsDict[Landmark.LeftFootIndex].transform.position, Color.cyan);

        Debug.DrawLine(jointObjectsDict[Landmark.RightAnkle].transform.position, jointObjectsDict[Landmark.RightHeel].transform.position, Color.red);
        Debug.DrawLine(jointObjectsDict[Landmark.RightAnkle].transform.position, jointObjectsDict[Landmark.RightFootIndex].transform.position, Color.red);
    }

    void OnApplicationQuit()
    {
        receiveThread?.Abort();
        udpClient?.Close();
    }
}