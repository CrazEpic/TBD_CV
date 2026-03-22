using UnityEngine;
using System.Net;
using System.Net.Sockets;
using System.Threading;

public class UDPReceiver : MonoBehaviour
{
    public int port = 5005;
    public int numJoints = 33;

    private UdpClient udpClient;
    private Thread receiveThread;
    private readonly object lockObject = new();
    private Vector3[] jointPositions;

    public GameObject jointPrefab;
    public GameObject[] jointObjects;

    void Start()
    {
        jointObjects = new GameObject[numJoints];
        for (int i = 0; i < numJoints; i++)
        {
            jointObjects[i] = Instantiate(jointPrefab);
            jointObjects[i].name = "Joint_" + (i + 1);
        }

        jointPositions = new Vector3[numJoints];
        udpClient = new UdpClient(port);
        receiveThread = new Thread(new ThreadStart(ReceiveData))
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
                {
                    floats[i] = System.BitConverter.ToSingle(data, i * 4);
                }

                lock (lockObject)
                {
                    // Map to Vector3 array
                    for (int i = 0; i < numJoints; i++)
                    {
                        jointPositions[i] = new Vector3(
                            -floats[i * 3 + 0],
                            -floats[i * 3 + 1],
                            -floats[i * 3 + 2]
                        );
                    }
                }
            }
            catch { }
        }
    }

    void Update()
    {
        // Example: print first joint
        if (jointPositions != null)
        {
            // Debug.Log(jointPositions[0]);
            // Here you can call your AvatarController.UpdateAvatar(jointPositions)

            lock (lockObject)
            {
                for (int i = 0; i < numJoints; i++)
                {
                    if (jointObjects[i] != null)
                    {
                        jointObjects[i].transform.position = jointPositions[i] * 5f;
                    }
                }
            }
        }
    }

    void OnApplicationQuit()
    {
        receiveThread?.Abort();
        udpClient?.Close();
    }
}