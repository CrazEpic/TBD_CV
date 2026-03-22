using System.Collections.Generic;
using UnityEngine;

public class AvatarController : MonoBehaviour
{
    public Animator animator;

    [Header("Avatar Root")]
    public Transform avatarRoot;
    public float scale = 1.0f;

    [Header("Axis Flip Settings")]
    public bool flipX = false;
    public bool flipY = false;
    public bool flipZ = false;

    [Header("Smoothing")]
    public float rotationSmooth = 12f;

    Quaternion initialRotation;

    void Start()
    {
        Transform leftUpperArm = animator.GetBoneTransform(HumanBodyBones.LeftUpperArm);
        initialRotation = leftUpperArm.rotation;
    }

    void LateUpdate()
    {
        Transform leftUpperArm = animator.GetBoneTransform(HumanBodyBones.LeftUpperArm);

        Vector3 shoulderPos = InstanceManager.Instance.mediapipeUDP.landmarksDict[MediapipeUDP.Landmark.RightShoulder];
        Vector3 elbowPos = InstanceManager.Instance.mediapipeUDP.landmarksDict[MediapipeUDP.Landmark.RightElbow];
        Vector3 direction = elbowPos - shoulderPos;

        if (direction.sqrMagnitude < 0.0001f) return;

        direction.Normalize();

        // --- Compute the target rotation in world space ---
        // Align -X of the bone with the direction vector
        Quaternion targetRotation = Quaternion.FromToRotation(-leftUpperArm.right, direction) * leftUpperArm.rotation;

        // --- Debug: print rotation in Euler angles for easier reading ---
        Vector3 euler = targetRotation.eulerAngles;
        // Debug.Log($"[Shoulder Target Rotation] Quaternion: {targetRotation}, Euler: {euler}");

        // --- Optional: debug lines to visualize the rotation ---
        Vector3 boneTargetDir = targetRotation * -Vector3.right;
        Debug.DrawLine(leftUpperArm.position, leftUpperArm.position + boneTargetDir, Color.magenta); // Target direction
        Debug.DrawLine(leftUpperArm.position, leftUpperArm.position + leftUpperArm.forward, Color.blue);
        Debug.DrawLine(leftUpperArm.position, leftUpperArm.position + leftUpperArm.up, Color.green);
        Debug.DrawLine(leftUpperArm.position, leftUpperArm.position + leftUpperArm.right, Color.red);
        Debug.DrawLine(leftUpperArm.position, leftUpperArm.position - leftUpperArm.right, Color.yellow);

        leftUpperArm.rotation = targetRotation;
        // --- Apply rotation smoothly if needed ---
        // float smooth = 12f;
        // leftUpperArm.rotation = Quaternion.Slerp(leftUpperArm.rotation, targetRotation, Time.deltaTime * smooth);
    }
}