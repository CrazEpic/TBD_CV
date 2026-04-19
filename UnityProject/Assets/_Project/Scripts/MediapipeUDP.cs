using UnityEngine;
using System;
using System.Net;
using System.Net.Sockets;
using System.Threading;
using System.Collections.Generic;
using System.Collections;
using System.Text;

public class MediapipeUDP : MonoBehaviour
{
    public int port = 5005;
    public int numJoints = 75;

    private UdpClient udpClient;
    private Thread receiveThread;
    public readonly object lockObject = new();

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
    public Vector3 instrumentCenter;
    public Vector3 instrumentAxis;
    public Vector3 instrumentUp;
    public float instrumentConfidence;

    public bool hybridStateValid;
    public Dictionary<string, Vector3> hybridJointPositions;
    public Dictionary<string, Quaternion> hybridJointRotations;
    public Dictionary<string, float> hybridJointConfidences;
    public Dictionary<string, float> hybridContactErrors;

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

        instrumentCenter = Vector3.zero;
        instrumentAxis = Vector3.zero;
        instrumentUp = Vector3.zero;
        instrumentConfidence = 0f;

        hybridStateValid = false;
        hybridJointPositions = new Dictionary<string, Vector3>();
        hybridJointRotations = new Dictionary<string, Quaternion>();
        hybridJointConfidences = new Dictionary<string, float>();
        hybridContactErrors = new Dictionary<string, float>();


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

                if (!LooksLikeJson(data))
                {
                    continue;
                }

                lock (lockObject)
                {
                    ParseHybridJsonPacket(data);
                }
            }
            catch { }
        }
    }

    bool LooksLikeJson(byte[] data)
    {
        if (data == null || data.Length == 0) return false;
        byte b = data[0];
        return b == (byte)'{' || b == (byte)'[';
    }

    void ParseHybridJsonPacket(byte[] data)
    {
        string text = Encoding.UTF8.GetString(data);
        object rootObj = MiniJSON.Deserialize(text);
        if (!(rootObj is Dictionary<string, object> root))
        {
            return;
        }

        if (!root.TryGetValue("type", out object typeObj))
        {
            return;
        }
        if (!string.Equals(typeObj as string, "hybrid_state_v2", StringComparison.Ordinal))
        {
            return;
        }

        if (!TryGetDict(root, "data", out Dictionary<string, object> dataDict))
        {
            return;
        }

        hybridStateValid = true;

        if (TryGetDict(dataDict, "human_joints", out Dictionary<string, object> humanJoints))
        {
            ParseHumanJoints(humanJoints);
        }

        if (TryGetDict(dataDict, "instrument", out Dictionary<string, object> instrumentDict))
        {
            ParseInstrumentState(instrumentDict);
        }

        if (TryGetDict(dataDict, "contacts", out Dictionary<string, object> contactsDict))
        {
            hybridContactErrors.Clear();
            foreach (var kv in contactsDict)
            {
                if (TryToFloat(kv.Value, out float v))
                {
                    hybridContactErrors[kv.Key] = v;
                }
            }
        }
    }

    void ParseHumanJoints(Dictionary<string, object> humanJoints)
    {
        hybridJointPositions.Clear();
        hybridJointRotations.Clear();
        hybridJointConfidences.Clear();

        foreach (var kv in humanJoints)
        {
            if (!(kv.Value is Dictionary<string, object> joint))
            {
                continue;
            }

            if (!TryGetVec3(joint, "position", out Vector3 pos))
            {
                continue;
            }

            if (flipX) pos.x = -pos.x;
            if (flipY) pos.y = -pos.y;
            if (flipZ) pos.z = -pos.z;

            Vector4 rot4 = new Vector4(0f, 0f, 0f, 1f);
            if (TryGetVec4(joint, "rotation", out Vector4 q))
            {
                rot4 = q;
            }

            Quaternion rot = new Quaternion(rot4.x, rot4.y, rot4.z, rot4.w).normalized;
            if (flipX) rot = new Quaternion(-rot.x, rot.y, rot.z, rot.w);
            if (flipY) rot = new Quaternion(rot.x, -rot.y, rot.z, rot.w);
            if (flipZ) rot = new Quaternion(rot.x, rot.y, -rot.z, rot.w);

            float conf = 0f;
            if (joint.TryGetValue("confidence", out object confObj) && TryToFloat(confObj, out float parsed))
            {
                conf = parsed;
            }

            hybridJointPositions[kv.Key] = pos;
            hybridJointRotations[kv.Key] = rot;
            hybridJointConfidences[kv.Key] = conf;

            if (kv.Key.StartsWith("pose_", StringComparison.Ordinal) && int.TryParse(kv.Key.Substring(5), out int poseIndex))
            {
                if (poseIndex >= 0 && poseIndex < 33)
                {
                    PoseLandmark lm = (PoseLandmark)poseIndex;
                    poseLandmarksDict[lm] = pos;
                    poseVisibilitiesDict[lm] = conf;
                }
            }
            else if (kv.Key.StartsWith("left_", StringComparison.Ordinal) && int.TryParse(kv.Key.Substring(5), out int lIndex))
            {
                if (lIndex >= 0 && lIndex < 21)
                {
                    HandLandmark lm = (HandLandmark)lIndex;
                    leftHandLandmarksDict[lm] = pos;
                    leftHandVisibilitiesDict[lm] = conf;
                }
            }
            else if (kv.Key.StartsWith("right_", StringComparison.Ordinal) && int.TryParse(kv.Key.Substring(6), out int rIndex))
            {
                if (rIndex >= 0 && rIndex < 21)
                {
                    HandLandmark lm = (HandLandmark)rIndex;
                    rightHandLandmarksDict[lm] = pos;
                    rightHandVisibilitiesDict[lm] = conf;
                }
            }
        }
    }

    void ParseInstrumentState(Dictionary<string, object> instrumentDict)
    {
        if (TryGetVec3(instrumentDict, "position", out Vector3 pos))
        {
            if (flipX) pos.x = -pos.x;
            if (flipY) pos.y = -pos.y;
            if (flipZ) pos.z = -pos.z;
            instrumentCenter = pos;
        }

        if (TryGetVec4(instrumentDict, "rotation", out Vector4 qv))
        {
            Quaternion q = new Quaternion(qv.x, qv.y, qv.z, qv.w).normalized;
            Vector3 axis = q * Vector3.right;
            Vector3 up = q * Vector3.up;
            if (flipX) { axis.x = -axis.x; up.x = -up.x; }
            if (flipY) { axis.y = -axis.y; up.y = -up.y; }
            if (flipZ) { axis.z = -axis.z; up.z = -up.z; }
            instrumentAxis = axis;
            instrumentUp = up;
        }

        if (instrumentDict.TryGetValue("confidence", out object confObj) && TryToFloat(confObj, out float conf))
        {
            instrumentConfidence = conf;
        }
    }

    static bool TryGetDict(Dictionary<string, object> dict, string key, out Dictionary<string, object> outDict)
    {
        outDict = null;
        if (!dict.TryGetValue(key, out object obj)) return false;
        outDict = obj as Dictionary<string, object>;
        return outDict != null;
    }

    static bool TryGetVec3(Dictionary<string, object> dict, string key, out Vector3 v)
    {
        v = Vector3.zero;
        if (!dict.TryGetValue(key, out object obj)) return false;
        if (!(obj is IList list) || list.Count < 3) return false;
        if (!TryToFloat(list[0], out float x)) return false;
        if (!TryToFloat(list[1], out float y)) return false;
        if (!TryToFloat(list[2], out float z)) return false;
        v = new Vector3(x, y, z);
        return true;
    }

    static bool TryGetVec4(Dictionary<string, object> dict, string key, out Vector4 v)
    {
        v = new Vector4(0f, 0f, 0f, 1f);
        if (!dict.TryGetValue(key, out object obj)) return false;
        if (!(obj is IList list) || list.Count < 4) return false;
        if (!TryToFloat(list[0], out float x)) return false;
        if (!TryToFloat(list[1], out float y)) return false;
        if (!TryToFloat(list[2], out float z)) return false;
        if (!TryToFloat(list[3], out float w)) return false;
        v = new Vector4(x, y, z, w);
        return true;
    }

    static bool TryToFloat(object obj, out float value)
    {
        value = 0f;
        if (obj == null) return false;
        switch (obj)
        {
            case float f:
                value = f;
                return true;
            case double d:
                value = (float)d;
                return true;
            case long l:
                value = l;
                return true;
            case int i:
                value = i;
                return true;
            case string s when float.TryParse(s, out float parsed):
                value = parsed;
                return true;
            default:
                return false;
        }
    }

    public Vector3 WorldToInstrumentLocal(Vector3 world)
    {
        if (instrumentConfidence <= 0.01f || instrumentAxis.sqrMagnitude < 1e-8f || instrumentUp.sqrMagnitude < 1e-8f)
        {
            return Vector3.zero;
        }

        Vector3 x = instrumentAxis.normalized;
        Vector3 y = instrumentUp.normalized;
        Vector3 z = Vector3.Cross(x, y);
        if (z.sqrMagnitude < 1e-8f) return Vector3.zero;
        z.Normalize();

        Vector3 delta = world - instrumentCenter;
        return new Vector3(Vector3.Dot(delta, x), Vector3.Dot(delta, y), Vector3.Dot(delta, z));
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

            // left hand
            Vector3 wristLHand = leftHandLandmarksDict[HandLandmark.Wrist];
            Vector3 wristLPose = poseLandmarksDict[PoseLandmark.LeftWrist];
            float scale = 1f; // change if bad

            foreach (var kv in leftHandLandmarksDict)
            {
                HandLandmark lm = kv.Key;

                Vector3 localOffset = kv.Value - wristLHand;

                leftHandObjectsDict[lm].transform.position = wristLPose + localOffset * scale + jointObjectsOffset;
            }

            // right hand
            Vector3 wristRHand = rightHandLandmarksDict[HandLandmark.Wrist];
            Vector3 wristRPose = poseLandmarksDict[PoseLandmark.RightWrist];

            foreach (var kv in rightHandLandmarksDict)
            {
                HandLandmark lm = kv.Key;

                Vector3 localOffset = kv.Value - wristRHand;

                rightHandObjectsDict[lm].transform.position = wristRPose + localOffset * scale + jointObjectsOffset;
            }

            if (instrumentConfidence > 0.01f)
            {
                Debug.DrawLine(
                    instrumentCenter + jointObjectsOffset,
                    instrumentCenter + instrumentAxis.normalized * 0.25f + jointObjectsOffset,
                    Color.green
                );

                Debug.DrawLine(
                    instrumentCenter + jointObjectsOffset,
                    instrumentCenter + instrumentUp.normalized * 0.18f + jointObjectsOffset,
                    Color.yellow
                );
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