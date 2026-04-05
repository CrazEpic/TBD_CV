using UnityEngine;

public class AvatarController : MonoBehaviour
{
    public Animator animator;

    public bool debugMode = false;
    public float smoothFactor = 15f;

    void LateUpdate()
    {
        if (animator == null || InstanceManager.Instance.mediapipeUDP == null) return;

        // ApplyTorso();
        // ApplyArms();
        // ApplyLegs();
        ApplyHands();
    }

    Vector3 L(MediapipeUDP.PoseLandmark l)
    {
        return InstanceManager.Instance.mediapipeUDP.poseLandmarksDict[l];
    }

    Vector3 H(MediapipeUDP.HandLandmark h, bool left = true)
    {
        return (left) ?
            InstanceManager.Instance.mediapipeUDP.leftHandLandmarksDict[h] :
            InstanceManager.Instance.mediapipeUDP.rightHandLandmarksDict[h];
    }

    void ApplyTorso()
    {
        Transform hips = animator.GetBoneTransform(HumanBodyBones.Hips);
        Transform spine = animator.GetBoneTransform(HumanBodyBones.Spine);
        Transform chest = animator.GetBoneTransform(HumanBodyBones.Chest);
        Transform upperChest = animator.GetBoneTransform(HumanBodyBones.UpperChest);

        Vector3 leftHip = L(MediapipeUDP.PoseLandmark.LeftHip);
        Vector3 rightHip = L(MediapipeUDP.PoseLandmark.RightHip);
        Vector3 leftShoulder = L(MediapipeUDP.PoseLandmark.LeftShoulder);
        Vector3 rightShoulder = L(MediapipeUDP.PoseLandmark.RightShoulder);

        // Centers
        Vector3 hipCenter = (leftHip + rightHip) * 0.5f;
        Vector3 shoulderCenter = (leftShoulder + rightShoulder) * 0.5f;

        // Axes
        Vector3 up = (shoulderCenter - hipCenter).normalized;
        Vector3 right = (rightHip - leftHip).normalized;
        Vector3 forward = -Vector3.Cross(right, up).normalized;

        Quaternion targetRotation = Quaternion.LookRotation(forward, up);

        if (debugMode)
        {
            Debug.DrawLine(hipCenter, hipCenter + up * 0.3f, Color.blue);
            Debug.DrawLine(hipCenter, hipCenter + forward * 0.3f, Color.red);
            Debug.DrawLine(hipCenter, hipCenter + right * 0.3f, Color.green);
        }

        // Apply distributed rotation
        hips.rotation = Quaternion.Slerp(hips.rotation, targetRotation, Time.deltaTime * smoothFactor);
        spine.rotation = Quaternion.Slerp(spine.rotation, targetRotation, Time.deltaTime * smoothFactor);
        chest.rotation = Quaternion.Slerp(chest.rotation, targetRotation, Time.deltaTime * smoothFactor);

        upperChest.rotation = Quaternion.Slerp(upperChest.rotation, targetRotation, Time.deltaTime * smoothFactor);
    }

    void ApplyRotation(Transform bone, Vector3 boneAxisToAlign, Vector3 targetDirection)
    {
        if (targetDirection.sqrMagnitude < 0.0001f) return;

        targetDirection.Normalize();

        // Compute the target rotation in world space
        Quaternion targetRotation = Quaternion.FromToRotation(boneAxisToAlign, targetDirection) * bone.rotation;

        if (debugMode)
        {
            Debug.DrawLine(bone.position, bone.position + targetDirection * 0.3f, Color.green); // Target direction
        }

        // Apply the rotation
        // bone.rotation = targetRotation;
        bone.rotation = Quaternion.Slerp(bone.rotation, targetRotation, Time.deltaTime * smoothFactor);
    }

    void ApplyArms()
    {
        Transform leftUpperArm = animator.GetBoneTransform(HumanBodyBones.LeftUpperArm);
        Transform leftLowerArm = animator.GetBoneTransform(HumanBodyBones.LeftLowerArm);
        Transform leftHand = animator.GetBoneTransform(HumanBodyBones.LeftHand);
        ApplyRotation(leftUpperArm, -leftUpperArm.right, L(MediapipeUDP.PoseLandmark.RightElbow) - L(MediapipeUDP.PoseLandmark.RightShoulder));
        ApplyRotation(leftLowerArm, -leftLowerArm.right, L(MediapipeUDP.PoseLandmark.RightWrist) - L(MediapipeUDP.PoseLandmark.RightElbow));
        ApplyRotation(leftHand, -leftHand.right, L(MediapipeUDP.PoseLandmark.RightIndex) - L(MediapipeUDP.PoseLandmark.RightWrist));

        Transform rightUpperArm = animator.GetBoneTransform(HumanBodyBones.RightUpperArm);
        Transform rightLowerArm = animator.GetBoneTransform(HumanBodyBones.RightLowerArm);
        Transform rightHand = animator.GetBoneTransform(HumanBodyBones.RightHand);
        ApplyRotation(rightUpperArm, rightUpperArm.right, L(MediapipeUDP.PoseLandmark.LeftElbow) - L(MediapipeUDP.PoseLandmark.LeftShoulder));
        ApplyRotation(rightLowerArm, rightLowerArm.right, L(MediapipeUDP.PoseLandmark.LeftWrist) - L(MediapipeUDP.PoseLandmark.LeftElbow));
        ApplyRotation(rightHand, rightHand.right, L(MediapipeUDP.PoseLandmark.LeftIndex) - L(MediapipeUDP.PoseLandmark.LeftWrist));
    }

    void ApplyLegs()
    {
        Transform leftUpperLeg = animator.GetBoneTransform(HumanBodyBones.LeftUpperLeg);
        Transform leftLowerLeg = animator.GetBoneTransform(HumanBodyBones.LeftLowerLeg);
        Transform leftFoot = animator.GetBoneTransform(HumanBodyBones.LeftFoot);
        ApplyRotation(leftUpperLeg, -leftUpperLeg.up, L(MediapipeUDP.PoseLandmark.RightKnee) - L(MediapipeUDP.PoseLandmark.RightHip));
        ApplyRotation(leftLowerLeg, -leftLowerLeg.up, L(MediapipeUDP.PoseLandmark.RightAnkle) - L(MediapipeUDP.PoseLandmark.RightKnee));
        ApplyRotation(leftFoot, leftFoot.forward, L(MediapipeUDP.PoseLandmark.RightFootIndex) - L(MediapipeUDP.PoseLandmark.RightAnkle));

        Transform rightUpperLeg = animator.GetBoneTransform(HumanBodyBones.RightUpperLeg);
        Transform rightLowerLeg = animator.GetBoneTransform(HumanBodyBones.RightLowerLeg);
        Transform rightFoot = animator.GetBoneTransform(HumanBodyBones.RightFoot);
        ApplyRotation(rightUpperLeg, -rightUpperLeg.up, L(MediapipeUDP.PoseLandmark.LeftKnee) - L(MediapipeUDP.PoseLandmark.LeftHip));
        ApplyRotation(rightLowerLeg, -rightLowerLeg.up, L(MediapipeUDP.PoseLandmark.LeftAnkle) - L(MediapipeUDP.PoseLandmark.LeftKnee));
        ApplyRotation(rightFoot, rightFoot.forward, L(MediapipeUDP.PoseLandmark.LeftFootIndex) - L(MediapipeUDP.PoseLandmark.LeftAnkle));
    }

    void ApplyHands()
    {
        // Transform leftThumbProximal = animator.GetBoneTransform(HumanBodyBones.LeftThumbProximal);
        // Transform leftThumbIntermediate = animator.GetBoneTransform(HumanBodyBones.LeftThumbIntermediate);
        // Transform leftThumbDistal = animator.GetBoneTransform(HumanBodyBones.LeftThumbDistal);

        // left thumb
        // LEFT THUMB HERE

        
        // left index
        Transform leftIndexProximal = animator.GetBoneTransform(HumanBodyBones.LeftIndexProximal);
        Transform leftIndexIntermediate = animator.GetBoneTransform(HumanBodyBones.LeftIndexIntermediate);
        Transform leftIndexDistal = animator.GetBoneTransform(HumanBodyBones.LeftIndexDistal);

        ApplyRotation(leftIndexProximal, -leftIndexProximal.right, H(MediapipeUDP.HandLandmark.IndexFingerPIP) - H(MediapipeUDP.HandLandmark.IndexFingerMCP));
        ApplyRotation(leftIndexIntermediate, -leftIndexIntermediate.right, H(MediapipeUDP.HandLandmark.IndexFingerDIP) - H(MediapipeUDP.HandLandmark.IndexFingerPIP));
        ApplyRotation(leftIndexDistal, -leftIndexDistal.right, H(MediapipeUDP.HandLandmark.IndexFingerTIP) - H(MediapipeUDP.HandLandmark.IndexFingerDIP));

        // left middle
        Transform leftMiddleProximal = animator.GetBoneTransform(HumanBodyBones.LeftMiddleProximal);
        Transform leftMiddleIntermediate = animator.GetBoneTransform(HumanBodyBones.LeftMiddleIntermediate);
        Transform leftMiddleDistal = animator.GetBoneTransform(HumanBodyBones.LeftMiddleDistal);

        ApplyRotation(leftMiddleProximal, -leftMiddleProximal.right, H(MediapipeUDP.HandLandmark.MiddleFingerPIP) - H(MediapipeUDP.HandLandmark.MiddleFingerMCP));
        ApplyRotation(leftMiddleIntermediate, -leftMiddleIntermediate.right, H(MediapipeUDP.HandLandmark.MiddleFingerDIP) - H(MediapipeUDP.HandLandmark.MiddleFingerPIP));
        ApplyRotation(leftMiddleDistal, -leftMiddleDistal.right, H(MediapipeUDP.HandLandmark.MiddleFingerTIP) - H(MediapipeUDP.HandLandmark.MiddleFingerDIP));

        // left ring
        Transform leftRingProximal = animator.GetBoneTransform(HumanBodyBones.LeftRingProximal);
        Transform leftRingIntermediate = animator.GetBoneTransform(HumanBodyBones.LeftRingIntermediate);
        Transform leftRingDistal = animator.GetBoneTransform(HumanBodyBones.LeftRingDistal);

        ApplyRotation(leftRingProximal, -leftRingProximal.right, H(MediapipeUDP.HandLandmark.RingFingerPIP) - H(MediapipeUDP.HandLandmark.RingFingerMCP));
        ApplyRotation(leftRingIntermediate, -leftRingIntermediate.right, H(MediapipeUDP.HandLandmark.RingFingerDIP) - H(MediapipeUDP.HandLandmark.RingFingerPIP));
        ApplyRotation(leftRingDistal, -leftRingDistal.right, H(MediapipeUDP.HandLandmark.RingFingerTIP) - H(MediapipeUDP.HandLandmark.RingFingerDIP));

        // left pinky
        Transform leftLittleProximal = animator.GetBoneTransform(HumanBodyBones.LeftLittleProximal);
        Transform leftLittleIntermediate = animator.GetBoneTransform(HumanBodyBones.LeftLittleIntermediate);
        Transform leftLittleDistal = animator.GetBoneTransform(HumanBodyBones.LeftLittleDistal);

        ApplyRotation(leftLittleProximal, -leftLittleProximal.right, H(MediapipeUDP.HandLandmark.PinkyPIP) - H(MediapipeUDP.HandLandmark.PinkyMCP));
        ApplyRotation(leftLittleIntermediate, -leftLittleIntermediate.right, H(MediapipeUDP.HandLandmark.PinkyDIP) - H(MediapipeUDP.HandLandmark.PinkyPIP));
        ApplyRotation(leftLittleDistal, -leftLittleDistal.right, H(MediapipeUDP.HandLandmark.PinkyTIP) - H(MediapipeUDP.HandLandmark.PinkyDIP));

        // right thumb
        // RIGHT THUMB HERE

        // right index
        Transform rightIndexProximal = animator.GetBoneTransform(HumanBodyBones.RightIndexProximal);
        Transform rightIndexIntermediate = animator.GetBoneTransform(HumanBodyBones.RightIndexIntermediate);
        Transform rightIndexDistal = animator.GetBoneTransform(HumanBodyBones.RightIndexDistal);

        ApplyRotation(rightIndexProximal, rightIndexProximal.right, H(MediapipeUDP.HandLandmark.IndexFingerPIP, false) - H(MediapipeUDP.HandLandmark.IndexFingerMCP, false));
        ApplyRotation(rightIndexIntermediate, rightIndexIntermediate.right, H(MediapipeUDP.HandLandmark.IndexFingerDIP, false) - H(MediapipeUDP.HandLandmark.IndexFingerPIP, false));
        ApplyRotation(rightIndexDistal, rightIndexDistal.right, H(MediapipeUDP.HandLandmark.IndexFingerTIP, false) - H(MediapipeUDP.HandLandmark.IndexFingerDIP, false));

        // right middle
        Transform rightMiddleProximal = animator.GetBoneTransform(HumanBodyBones.RightMiddleProximal);
        Transform rightMiddleIntermediate = animator.GetBoneTransform(HumanBodyBones.RightMiddleIntermediate);
        Transform rightMiddleDistal = animator.GetBoneTransform(HumanBodyBones.RightMiddleDistal);

        ApplyRotation(rightMiddleProximal, rightMiddleProximal.right, H(MediapipeUDP.HandLandmark.MiddleFingerPIP, false) - H(MediapipeUDP.HandLandmark.MiddleFingerMCP, false));
        ApplyRotation(rightMiddleIntermediate, rightMiddleIntermediate.right, H(MediapipeUDP.HandLandmark.MiddleFingerDIP, false) - H(MediapipeUDP.HandLandmark.MiddleFingerPIP, false));
        ApplyRotation(rightMiddleDistal, rightMiddleDistal.right, H(MediapipeUDP.HandLandmark.MiddleFingerTIP, false) - H(MediapipeUDP.HandLandmark.MiddleFingerDIP, false));

        // right ring
        Transform rightRingProximal = animator.GetBoneTransform(HumanBodyBones.RightRingProximal);
        Transform rightRingIntermediate = animator.GetBoneTransform(HumanBodyBones.RightRingIntermediate);
        Transform rightRingDistal = animator.GetBoneTransform(HumanBodyBones.RightRingDistal);

        ApplyRotation(rightRingProximal, rightRingProximal.right, H(MediapipeUDP.HandLandmark.RingFingerPIP, false) - H(MediapipeUDP.HandLandmark.RingFingerMCP, false));
        ApplyRotation(rightRingIntermediate, rightRingIntermediate.right, H(MediapipeUDP.HandLandmark.RingFingerDIP, false) - H(MediapipeUDP.HandLandmark.RingFingerPIP, false));
        ApplyRotation(rightRingDistal, rightRingDistal.right, H(MediapipeUDP.HandLandmark.RingFingerTIP, false) - H(MediapipeUDP.HandLandmark.RingFingerDIP, false));

        // right pinky
        Transform rightLittleProximal = animator.GetBoneTransform(HumanBodyBones.RightLittleProximal);
        Transform rightLittleIntermediate = animator.GetBoneTransform(HumanBodyBones.RightLittleIntermediate);
        Transform rightLittleDistal = animator.GetBoneTransform(HumanBodyBones.RightLittleDistal);

        ApplyRotation(rightLittleProximal, rightLittleProximal.right, H(MediapipeUDP.HandLandmark.PinkyPIP, false) - H(MediapipeUDP.HandLandmark.PinkyMCP, false));
        ApplyRotation(rightLittleIntermediate, rightLittleIntermediate.right, H(MediapipeUDP.HandLandmark.PinkyDIP, false) - H(MediapipeUDP.HandLandmark.PinkyPIP, false));
        ApplyRotation(rightLittleDistal, rightLittleDistal.right, H(MediapipeUDP.HandLandmark.PinkyTIP, false) - H(MediapipeUDP.HandLandmark.PinkyDIP, false));

        // Transform leftUpperArm = animator.GetBoneTransform(HumanBodyBones.LeftUpperArm);
        // Transform leftLowerArm = animator.GetBoneTransform(HumanBodyBones.LeftLowerArm);
        // Transform leftHand = animator.GetBoneTransform(HumanBodyBones.LeftHand);
        // ApplyRotation(leftUpperArm, -leftUpperArm.right, L(MediapipeUDP.PoseLandmark.RightElbow) - L(MediapipeUDP.PoseLandmark.RightShoulder));
        // ApplyRotation(leftLowerArm, -leftLowerArm.right, L(MediapipeUDP.PoseLandmark.RightWrist) - L(MediapipeUDP.PoseLandmark.RightElbow));
        // ApplyRotation(leftHand, -leftHand.right, L(MediapipeUDP.PoseLandmark.RightIndex) - L(MediapipeUDP.PoseLandmark.RightWrist));
    }
}