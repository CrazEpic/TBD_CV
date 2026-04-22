#if UNITY_EDITOR
using UnityEditor;
using UnityEngine;

[CustomEditor(typeof(ViolinKeypointRig))]
public class ViolinKeypointRigEditor : Editor
{
    public override void OnInspectorGUI()
    {
        DrawDefaultInspector();

        ViolinKeypointRig rig = (ViolinKeypointRig)target;

        EditorGUILayout.Space(8f);
        EditorGUILayout.LabelField("Keypoint Workflow", EditorStyles.boldLabel);
        EditorGUILayout.HelpBox(
            "1) Click Generate Supplementary Template.\n" +
            "2) Move driver markers in Scene view (Unity units = meters).\n" +
            "3) Left-side mirrored points are shown as gizmos only (not scene objects).\n" +
            "4) String symmetry is enforced: A->D and E->G are mirrored across the violin midline (D/G are gizmos only).\n" +
            "5) Scene gizmos preview the derived PnP points (center/neck_end/body_end/chin_anchor) before export.\n" +
            "6) Exporter mirrors missing left-side points from right-side drivers and derives center/neck_end/body_end/chin_anchor when possible.\n" +
            "7) Click Export JSON and point Python --calibration-file to that file.",
            MessageType.Info
        );

        if (GUILayout.Button("Generate Supplementary Template"))
        {
            Undo.RegisterCompleteObjectUndo(rig.gameObject, "Generate Supplementary Keypoints");
            rig.EnsureSupplementaryTemplateKeypoints();
            EditorUtility.SetDirty(rig);
        }

        if (GUILayout.Button("Export Keypoints JSON"))
        {
            if (rig.TryExportToFile(out string msg))
            {
                EditorUtility.DisplayDialog("Violin Keypoints Exported", "Wrote: " + msg, "OK");
            }
            else
            {
                EditorUtility.DisplayDialog("Export Failed", msg, "OK");
            }
        }
    }

    private void OnSceneGUI()
    {
        ViolinKeypointRig rig = (ViolinKeypointRig)target;
        if (rig == null || rig.keypoints == null)
        {
            return;
        }

        Handles.color = new Color(1f, 0.9f, 0f, 1f);

        foreach (ViolinKeypointRig.KeypointBinding binding in rig.keypoints)
        {
            if (binding == null || binding.marker == null)
            {
                continue;
            }

            Transform marker = binding.marker;
            bool isLockedMirrored = ViolinKeypointRig.IsMirroredLeftKey(binding.key);

            if (!isLockedMirrored)
            {
                EditorGUI.BeginChangeCheck();
                Vector3 newPos = Handles.PositionHandle(marker.position, marker.rotation);
                if (EditorGUI.EndChangeCheck())
                {
                    Undo.RecordObject(marker, "Move Violin Keypoint");
                    marker.position = newPos;
                    EditorUtility.SetDirty(marker);
                    EditorUtility.SetDirty(rig);
                }
            }

            if (rig.drawLabels)
            {
                string label = isLockedMirrored ? binding.key + " (mirrored/locked)" : binding.key;
                Handles.Label(marker.position + Vector3.up * 0.01f, label);
            }
        }
    }
}
#endif
