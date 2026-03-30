using UnityEngine;
using System.Net;
using System.Net.Sockets;
using System.Threading;
using System.Collections.Generic;

public class MediapipeUDP : MonoBehaviour
{
    public int port = 5005;
    public int numJoints = 75;

    private UdpClient udpClient;
    private Thread receiveThread;
    private readonly object lockObject = new();

    // Typed enum for pose landmarks
    public enum PoseLandmark
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

    public enum HandLandmark
    {
        Wrist = 0, ThumbCMC = 1,
        ThumbMCP = 2, ThumbIP = 3,
        ThumbTIP = 4, IndexFingerMCP = 5,
        IndexFingerPIP = 6, IndexFingerDIP = 7,
        IndexFingerTIP = 8, MiddleFingerMCP = 9,
        MiddleFingerPIP = 10, MiddleFingerDIP = 11,
        MiddleFingerTIP = 12, RingFingerMCP = 13,
        RingFingerPIP = 14, RingFingerDIP = 15,
        RingFingerTIP = 16, PinkyMCP = 17,
        PinkyPIP = 18, PinkyDIP = 19,
        PinkyTIP = 20 
    }



    // Dictionary-based landmarks and visibilities
    //public Dictionary<PoseLandmark, Vector3> landmarksDict;
    public Dictionary<PoseLandmark, Vector3> poseLandmarksDict;
    public Dictionary<HandLandmark, Vector3> leftHandLandmarksDict;
    public Dictionary<HandLandmark, Vector3> rightHandLandmarksDict;
    public Dictionary<PoseLandmark, float> poseVisibilitiesDict;
    public Dictionary<HandLandmark, float> leftHandVisibilitiesDict;
    public Dictionary<HandLandmark, float> rightHandVisibilitiesDict;

    public GameObject jointPrefab;
    //public Dictionary<Landmark, GameObject> jointObjectsDict;
    public Dictionary<PoseLandmark, GameObject> poseObjectsDict;
    public Dictionary<HandLandmark, GameObject> leftHandObjectsDict;
    public Dictionary<HandLandmark, GameObject> rightHandObjectsDict;
    public Vector3 jointObjectsOffset = Vector3.zero;

    public bool flipX = false;
    public bool flipY = true;
    public bool flipZ = true;

    void Start()
    {
        poseObjectsDict = new Dictionary<PoseLandmark, GameObject>();
        poseLandmarksDict = new Dictionary<PoseLandmark, Vector3>();
        poseVisibilitiesDict = new Dictionary<PoseLandmark, float>();

        leftHandObjectsDict = new Dictionary<HandLandmark, GameObject>();
        leftHandLandmarksDict = new Dictionary<HandLandmark, Vector3>();
        leftHandVisibilitiesDict = new Dictionary<HandLandmark, float>();

        rightHandObjectsDict = new Dictionary<HandLandmark, GameObject>();
        rightHandLandmarksDict = new Dictionary<HandLandmark, Vector3>();
        rightHandVisibilitiesDict = new Dictionary<HandLandmark, float>();


        // Initialize dictionaries and GameObjects
        foreach (PoseLandmark lm in System.Enum.GetValues(typeof(PoseLandmark)))
        {
            poseLandmarksDict[lm] = Vector3.zero;
            poseVisibilitiesDict[lm] = 0f;

            GameObject jointObj = Instantiate(jointPrefab);
            jointObj.name = "Joint_" + lm.ToString();
            poseObjectsDict[lm] = jointObj;
        }

        foreach (HandLandmark lm in System.Enum.GetValues(typeof(HandLandmark)))
        {
            // left hand
            leftHandLandmarksDict[lm] = Vector3.zero;
            leftHandVisibilitiesDict[lm] = 0f;

            GameObject leftHandObj = Instantiate(jointPrefab);
            leftHandObj.name = "LeftHand_" + lm.ToString();
            leftHandObjectsDict[lm] = leftHandObj;

            // right hand
            rightHandLandmarksDict[lm] = Vector3.zero;
            rightHandVisibilitiesDict[lm] = 0f;

            GameObject rightHandObj = Instantiate(jointPrefab);
            rightHandObj.name = "rightHand_" + lm.ToString();
            rightHandObjectsDict[lm] = rightHandObj;
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
                    int index = 0; // each iteration, index will cycle through 4 values from flattened 4 dimensional vector array
                    // pose
                    for (int i = 0; i < 33; i++)
                    {
                        float x = floats[index++];
                        float y = floats[index++];
                        float z = floats[index++];

                        if (flipX) x = -x;
                        if (flipY) y = -y;
                        if (flipZ) z = -z;

                        PoseLandmark lm = (PoseLandmark)i;
                        poseLandmarksDict[lm] = new Vector3(x, y, z);
                        poseVisibilitiesDict[lm] = floats[index++];
                    }

                    // left hand
                    for (int i = 0; i < 21; i++)
                    {
                        float x = floats[index++];
                        float y = floats[index++];
                        float z = floats[index++];

                        if (flipX) x = -x;
                        if (flipY) y = -y;
                        if (flipZ) z = -z;

                        HandLandmark lm = (HandLandmark)i;
                        leftHandLandmarksDict[lm] = new Vector3(x, y, z);
                        leftHandVisibilitiesDict[lm] = floats[index++];
                    }

                    // right hand
                    for (int i = 0; i < 21; i++)
                    {
                        float x = floats[index++];
                        float y = floats[index++];
                        float z = floats[index++];

                        if (flipX) x = -x;
                        if (flipY) y = -y;
                        if (flipZ) z = -z;

                        HandLandmark lm = (HandLandmark)i;
                        rightHandLandmarksDict[lm] = new Vector3(x, y, z);
                        rightHandVisibilitiesDict[lm] = floats[index++];
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
            // foreach (PoseLandmark lm in System.Enum.GetValues(typeof(PoseLandmark)))
            // {
            //     GameObject jointObj = poseObjectsDict[lm];
            //     if (jointObj != null)
            //     {
            //         jointObj.transform.position = poseLandmarksDict[lm] + jointObjectsOffset;
            //     }
            // }

            // pose
            foreach (var kv in poseLandmarksDict)
            {
                PoseLandmark lm = kv.Key;

                if (poseObjectsDict.ContainsKey(lm))
                {
                    poseObjectsDict[lm].transform.position = kv.Value + jointObjectsOffset;
                }
            }

            foreach (var kv in leftHandLandmarksDict)
            {
                HandLandmark lm = kv.Key;

                if (leftHandObjectsDict.ContainsKey(lm))
                {
                    leftHandObjectsDict[lm].transform.position = kv.Value + jointObjectsOffset;
                }
            }

            foreach (var kv in rightHandLandmarksDict)
            {
                HandLandmark lm = kv.Key;

                if (rightHandObjectsDict.ContainsKey(lm))
                {
                    rightHandObjectsDict[lm].transform.position = kv.Value + jointObjectsOffset;
                }
            }

        }

        DrawSkeleton();
    }

    void DrawSkeleton()
    {
        // Head / Face
        Debug.DrawLine(poseObjectsDict[PoseLandmark.Nose].transform.position, poseObjectsDict[PoseLandmark.LeftEyeInner].transform.position, Color.cyan);
        Debug.DrawLine(poseObjectsDict[PoseLandmark.LeftEyeInner].transform.position, poseObjectsDict[PoseLandmark.LeftEye].transform.position, Color.cyan);
        Debug.DrawLine(poseObjectsDict[PoseLandmark.LeftEye].transform.position, poseObjectsDict[PoseLandmark.LeftEyeOuter].transform.position, Color.cyan);

        Debug.DrawLine(poseObjectsDict[PoseLandmark.Nose].transform.position, poseObjectsDict[PoseLandmark.RightEyeInner].transform.position, Color.red);
        Debug.DrawLine(poseObjectsDict[PoseLandmark.RightEyeInner].transform.position, poseObjectsDict[PoseLandmark.RightEye].transform.position, Color.red);
        Debug.DrawLine(poseObjectsDict[PoseLandmark.RightEye].transform.position, poseObjectsDict[PoseLandmark.RightEyeOuter].transform.position, Color.red);

        Debug.DrawLine(poseObjectsDict[PoseLandmark.Nose].transform.position, poseObjectsDict[PoseLandmark.MouthLeft].transform.position, Color.cyan);
        Debug.DrawLine(poseObjectsDict[PoseLandmark.Nose].transform.position, poseObjectsDict[PoseLandmark.MouthRight].transform.position, Color.red);

        // Shoulders & Arms
        Debug.DrawLine(poseObjectsDict[PoseLandmark.LeftShoulder].transform.position, poseObjectsDict[PoseLandmark.LeftElbow].transform.position, Color.cyan);
        Debug.DrawLine(poseObjectsDict[PoseLandmark.LeftElbow].transform.position, poseObjectsDict[PoseLandmark.LeftWrist].transform.position, Color.cyan);

        Debug.DrawLine(poseObjectsDict[PoseLandmark.RightShoulder].transform.position, poseObjectsDict[PoseLandmark.RightElbow].transform.position, Color.red);
        Debug.DrawLine(poseObjectsDict[PoseLandmark.RightElbow].transform.position, poseObjectsDict[PoseLandmark.RightWrist].transform.position, Color.red);

        Debug.DrawLine(poseObjectsDict[PoseLandmark.LeftShoulder].transform.position, poseObjectsDict[PoseLandmark.RightShoulder].transform.position, Color.yellow);

        // Hands / Fingers
        Debug.DrawLine(poseObjectsDict[PoseLandmark.LeftWrist].transform.position, poseObjectsDict[PoseLandmark.LeftPinky].transform.position, Color.blue);
        Debug.DrawLine(poseObjectsDict[PoseLandmark.LeftWrist].transform.position, poseObjectsDict[PoseLandmark.LeftIndex].transform.position, Color.blue);
        Debug.DrawLine(poseObjectsDict[PoseLandmark.LeftWrist].transform.position, poseObjectsDict[PoseLandmark.LeftThumb].transform.position, Color.blue);

        Debug.DrawLine(poseObjectsDict[PoseLandmark.RightWrist].transform.position, poseObjectsDict[PoseLandmark.RightPinky].transform.position, Color.magenta);
        Debug.DrawLine(poseObjectsDict[PoseLandmark.RightWrist].transform.position, poseObjectsDict[PoseLandmark.RightIndex].transform.position, Color.magenta);
        Debug.DrawLine(poseObjectsDict[PoseLandmark.RightWrist].transform.position, poseObjectsDict[PoseLandmark.RightThumb].transform.position, Color.magenta);

        // Torso
        Debug.DrawLine(poseObjectsDict[PoseLandmark.LeftShoulder].transform.position, poseObjectsDict[PoseLandmark.LeftHip].transform.position, Color.cyan);
        Debug.DrawLine(poseObjectsDict[PoseLandmark.RightShoulder].transform.position, poseObjectsDict[PoseLandmark.RightHip].transform.position, Color.red);
        Debug.DrawLine(poseObjectsDict[PoseLandmark.LeftHip].transform.position, poseObjectsDict[PoseLandmark.RightHip].transform.position, Color.yellow);

        // Legs
        Debug.DrawLine(poseObjectsDict[PoseLandmark.LeftHip].transform.position, poseObjectsDict[PoseLandmark.LeftKnee].transform.position, Color.cyan);
        Debug.DrawLine(poseObjectsDict[PoseLandmark.LeftKnee].transform.position, poseObjectsDict[PoseLandmark.LeftAnkle].transform.position, Color.cyan);

        Debug.DrawLine(poseObjectsDict[PoseLandmark.RightHip].transform.position, poseObjectsDict[PoseLandmark.RightKnee].transform.position, Color.red);
        Debug.DrawLine(poseObjectsDict[PoseLandmark.RightKnee].transform.position, poseObjectsDict[PoseLandmark.RightAnkle].transform.position, Color.red);

        // Feet
        Debug.DrawLine(poseObjectsDict[PoseLandmark.LeftAnkle].transform.position, poseObjectsDict[PoseLandmark.LeftHeel].transform.position, Color.cyan);
        Debug.DrawLine(poseObjectsDict[PoseLandmark.LeftAnkle].transform.position, poseObjectsDict[PoseLandmark.LeftFootIndex].transform.position, Color.cyan);

        Debug.DrawLine(poseObjectsDict[PoseLandmark.RightAnkle].transform.position, poseObjectsDict[PoseLandmark.RightHeel].transform.position, Color.red);
        Debug.DrawLine(poseObjectsDict[PoseLandmark.RightAnkle].transform.position, poseObjectsDict[PoseLandmark.RightFootIndex].transform.position, Color.red);
    }

    void OnApplicationQuit()
    {
        receiveThread?.Abort();
        udpClient?.Close();
    }
}