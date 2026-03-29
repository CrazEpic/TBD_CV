using UnityEngine;

public class AvatarController : MonoBehaviour
{
    public Animator animator;

    public bool debugMode = false;
    public float smoothFactor = 15f;

    void LateUpdate()
    {
        if (animator == null || InstanceManager.Instance.mediapipeUDP == null) return;

        ApplyTorso();
        ApplyArms();
        ApplyLegs();
    }

    Vector3 L(MediapipeUDP.Landmark l)
    {
        return InstanceManager.Instance.mediapipeUDP.landmarksDict[l];
    }

    void ApplyTorso()
    {
        Transform hips = animator.GetBoneTransform(HumanBodyBones.Hips);
        Transform spine = animator.GetBoneTransform(HumanBodyBones.Spine);
        Transform chest = animator.GetBoneTransform(HumanBodyBones.Chest);
        Transform upperChest = animator.GetBoneTransform(HumanBodyBones.UpperChest);

        Vector3 leftHip = L(MediapipeUDP.Landmark.LeftHip);
        Vector3 rightHip = L(MediapipeUDP.Landmark.RightHip);
        Vector3 leftShoulder = L(MediapipeUDP.Landmark.LeftShoulder);
        Vector3 rightShoulder = L(MediapipeUDP.Landmark.RightShoulder);

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
        ApplyRotation(leftUpperArm, -leftUpperArm.right, L(MediapipeUDP.Landmark.RightElbow) - L(MediapipeUDP.Landmark.RightShoulder));
        ApplyRotation(leftLowerArm, -leftLowerArm.right, L(MediapipeUDP.Landmark.RightWrist) - L(MediapipeUDP.Landmark.RightElbow));
        ApplyRotation(leftHand, -leftHand.right, L(MediapipeUDP.Landmark.RightIndex) - L(MediapipeUDP.Landmark.RightWrist));

        Transform rightUpperArm = animator.GetBoneTransform(HumanBodyBones.RightUpperArm);
        Transform rightLowerArm = animator.GetBoneTransform(HumanBodyBones.RightLowerArm);
        Transform rightHand = animator.GetBoneTransform(HumanBodyBones.RightHand);
        ApplyRotation(rightUpperArm, rightUpperArm.right, L(MediapipeUDP.Landmark.LeftElbow) - L(MediapipeUDP.Landmark.LeftShoulder));
        ApplyRotation(rightLowerArm, rightLowerArm.right, L(MediapipeUDP.Landmark.LeftWrist) - L(MediapipeUDP.Landmark.LeftElbow));
        ApplyRotation(rightHand, rightHand.right, L(MediapipeUDP.Landmark.LeftIndex) - L(MediapipeUDP.Landmark.LeftWrist));
    }

    void ApplyLegs()
    {
        Transform leftUpperLeg = animator.GetBoneTransform(HumanBodyBones.LeftUpperLeg);
        Transform leftLowerLeg = animator.GetBoneTransform(HumanBodyBones.LeftLowerLeg);
        Transform leftFoot = animator.GetBoneTransform(HumanBodyBones.LeftFoot);
        ApplyRotation(leftUpperLeg, -leftUpperLeg.up, L(MediapipeUDP.Landmark.RightKnee) - L(MediapipeUDP.Landmark.RightHip));
        ApplyRotation(leftLowerLeg, -leftLowerLeg.up, L(MediapipeUDP.Landmark.RightAnkle) - L(MediapipeUDP.Landmark.RightKnee));
        ApplyRotation(leftFoot, leftFoot.forward, L(MediapipeUDP.Landmark.RightFootIndex) - L(MediapipeUDP.Landmark.RightAnkle));

        Transform rightUpperLeg = animator.GetBoneTransform(HumanBodyBones.RightUpperLeg);
        Transform rightLowerLeg = animator.GetBoneTransform(HumanBodyBones.RightLowerLeg);
        Transform rightFoot = animator.GetBoneTransform(HumanBodyBones.RightFoot);
        ApplyRotation(rightUpperLeg, -rightUpperLeg.up, L(MediapipeUDP.Landmark.LeftKnee) - L(MediapipeUDP.Landmark.LeftHip));
        ApplyRotation(rightLowerLeg, -rightLowerLeg.up, L(MediapipeUDP.Landmark.LeftAnkle) - L(MediapipeUDP.Landmark.LeftKnee));
        ApplyRotation(rightFoot, rightFoot.forward, L(MediapipeUDP.Landmark.LeftFootIndex) - L(MediapipeUDP.Landmark.LeftAnkle));
    }
}