using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using UnityEngine;

[ExecuteAlways]
public class ViolinKeypointRig : MonoBehaviour
{
    [Serializable]
    public class KeypointBinding
    {
        public string key = "center";
        public Transform marker;
    }

    [Header("Rig")]
    public Transform violinRoot;
    public List<KeypointBinding> keypoints = new List<KeypointBinding>();

    [Header("Editor")]
    public bool drawLabels = true;
    public float gizmoSize = 0.005f;

    [Header("Mirroring")]
    [Tooltip("When true, mirror across a fixed local X plane instead of estimating from keypoints.")]
    public bool useFixedMirrorCenterX = true;
    [Tooltip("Local-space X value for the mirror plane when Use Fixed Mirror Center X is enabled.")]
    public float fixedMirrorCenterX = 0.0f;

    [Tooltip("Path relative to UnityProject root. ../Demo/config/... writes into the Python app config folder.")]
    public string exportRelativePath = "../Demo/config/instrument_profiles.unity.json";

    public static readonly string[] RequiredKeys =
    {
        "center",
        "neck_end",
        "body_end",
        "chin_anchor",
    };

    private static readonly string[] SupplementaryTemplateKeys =
    {
        // Outline drivers: bottom center -> bottom right -> top right -> upper middle
        "outline_01_bottom_center",
        "outline_02_bottom_right_corner",
        "outline_03_top_right_corner",
        "outline_04_upper_middle_body_end",

        // Fingerboard drivers (right side). Left side is mirrored.
        "fingerboard_01_bridge_right_side",
        "fingerboard_02_nut_right_side",

        // String endpoints (2 points each)
        "string_G_bridge_side",
        "string_G_fingerboard_end",
        "string_D_bridge_side",
        "string_D_fingerboard_end",
        "string_A_bridge_side",
        "string_A_fingerboard_end",
        "string_E_bridge_side",
        "string_E_fingerboard_end",
    };

    private static readonly Vector3[] SupplementaryTemplateDefaults =
    {
        // Outline driver defaults
        new Vector3(0.00f, -0.14f, 0.000f),
        new Vector3(0.03f, -0.12f, -0.045f),
        new Vector3(0.03f,  0.08f, -0.035f),
        new Vector3(0.08f,  0.02f, 0.000f),

        // Fingerboard driver defaults (right side)
        new Vector3(0.05f,  0.035f, 0.000f),
        new Vector3(0.33f,  0.035f, 0.000f),

        // String endpoints defaults
        new Vector3(0.05f,  0.030f, 0.000f),
        new Vector3(0.33f,  0.030f, 0.000f),
        new Vector3(0.05f,  0.010f, 0.000f),
        new Vector3(0.33f,  0.010f, 0.000f),
        new Vector3(0.05f, -0.010f, 0.000f),
        new Vector3(0.33f, -0.010f, 0.000f),
        new Vector3(0.05f, -0.030f, 0.000f),
        new Vector3(0.33f, -0.030f, 0.000f),
    };

    public Transform RootOrSelf
    {
        get { return violinRoot != null ? violinRoot : transform; }
    }

    public void EnsureSupplementaryTemplateKeypoints()
    {
        Transform root = RootOrSelf;
        for (int i = 0; i < SupplementaryTemplateKeys.Length; i++)
        {
            EnsureKeypoint(root, SupplementaryTemplateKeys[i], SupplementaryTemplateDefaults[i]);
        }

    }

    private void EnsureKeypoint(Transform root, string key, Vector3 defaultLocalPosition)
    {
        KeypointBinding existing = keypoints.Find(k => string.Equals(k.key, key, StringComparison.Ordinal));
        if (existing != null && existing.marker != null)
        {
            return;
        }

        GameObject markerObj = new GameObject($"kp_{key}");
        markerObj.transform.SetParent(root, false);
        markerObj.transform.localPosition = defaultLocalPosition;
        markerObj.transform.localRotation = Quaternion.identity;

        if (existing == null)
        {
            existing = new KeypointBinding { key = key };
            keypoints.Add(existing);
        }

        existing.marker = markerObj.transform;
    }

    public bool TryBuildExport(out string json, out string error)
    {
        json = string.Empty;
        error = string.Empty;

        Dictionary<string, Vector3> positions = new Dictionary<string, Vector3>(StringComparer.Ordinal);
        Transform root = RootOrSelf;

        for (int i = 0; i < keypoints.Count; i++)
        {
            KeypointBinding binding = keypoints[i];
            if (binding == null || string.IsNullOrWhiteSpace(binding.key) || binding.marker == null)
            {
                continue;
            }

            Vector3 local = root.InverseTransformPoint(binding.marker.position);
            positions[binding.key.Trim()] = local;
        }

        DeriveMirroredSupplementaryKeypoints(positions, useFixedMirrorCenterX, fixedMirrorCenterX);
        DeriveRequiredKeypoints(positions);

        for (int i = 0; i < RequiredKeys.Length; i++)
        {
            if (!positions.ContainsKey(RequiredKeys[i]))
            {
                error = "Missing required keypoint: " + RequiredKeys[i];
                return false;
            }
        }

        json = BuildProfileJson(positions);
        return true;
    }

    private static void DeriveMirroredSupplementaryKeypoints(
        Dictionary<string, Vector3> positions,
        bool useFixedCenter,
        float fixedCenterX
    )
    {
        // For violins oriented toward +Z, left-right is along local X.
        float midX;
        if (useFixedCenter)
        {
            midX = fixedCenterX;
        }
        else if (!TryEstimateSymmetryMidX(positions, out midX))
        {
            return;
        }

        // Preferred descriptive naming pairs.
        MirrorPair(positions, "outline_02_bottom_right_corner", "outline_06_bottom_left_corner", midX);
        MirrorPair(positions, "outline_03_top_right_corner", "outline_05_top_left_corner", midX);
        MirrorPair(positions, "fingerboard_01_bridge_right_side", "fingerboard_04_bridge_left_side", midX);
        MirrorPair(positions, "fingerboard_02_nut_right_side", "fingerboard_03_nut_left_side", midX);

        // Legacy naming pairs for compatibility.
        MirrorPair(positions, "outline_02", "outline_06", midX);
        MirrorPair(positions, "outline_03", "outline_05", midX);
        MirrorPair(positions, "fingerboard_01", "fingerboard_04", midX);
        MirrorPair(positions, "fingerboard_02", "fingerboard_03", midX);
        MirrorPair(positions, "fingerboard_01_bridge_treble_side", "fingerboard_04_bridge_bass_side", midX);
        MirrorPair(positions, "fingerboard_02_nut_treble_side", "fingerboard_03_nut_bass_side", midX);
    }

    private static void MirrorPair(Dictionary<string, Vector3> positions, string rightKey, string leftKey, float midX)
    {
        bool hasRight = positions.TryGetValue(rightKey, out Vector3 right);
        bool hasLeft = positions.TryGetValue(leftKey, out Vector3 left);

        // Right side is authoritative when present; left is always mirrored from right.
        if (hasRight)
        {
            positions[leftKey] = MirrorAcrossMidX(right, midX);
        }
        else if (hasLeft)
        {
            positions[rightKey] = MirrorAcrossMidX(left, midX);
        }
    }

    public static bool IsMirroredLeftKey(string key)
    {
        if (string.IsNullOrWhiteSpace(key))
        {
            return false;
        }

        return string.Equals(key, "outline_05_top_left_corner", StringComparison.Ordinal)
            || string.Equals(key, "outline_06_bottom_left_corner", StringComparison.Ordinal)
            || string.Equals(key, "fingerboard_03_nut_left_side", StringComparison.Ordinal)
            || string.Equals(key, "fingerboard_04_bridge_left_side", StringComparison.Ordinal)
            // Legacy names kept for compatibility.
            || string.Equals(key, "outline_05", StringComparison.Ordinal)
            || string.Equals(key, "outline_06", StringComparison.Ordinal)
            || string.Equals(key, "fingerboard_03", StringComparison.Ordinal)
            || string.Equals(key, "fingerboard_04", StringComparison.Ordinal)
            || string.Equals(key, "fingerboard_03_nut_bass_side", StringComparison.Ordinal)
            || string.Equals(key, "fingerboard_04_bridge_bass_side", StringComparison.Ordinal);
    }

    private static Vector3 MirrorAcrossMidX(Vector3 p, float midX)
    {
        return new Vector3(2f * midX - p.x, p.y, p.z);
    }

    private static bool TryEstimateSymmetryMidX(Dictionary<string, Vector3> positions, out float midX)
    {
        List<float> xs = new List<float>();

        // Primary centerline hints.
        string[] middleKeys =
        {
            "center",
            "body_end",
            "neck_end",
            "outline_01_bottom_center",
            "outline_04_upper_middle_body_end",
            "outline_01",
            "outline_04",
        };

        for (int i = 0; i < middleKeys.Length; i++)
        {
            if (positions.TryGetValue(middleKeys[i], out Vector3 p))
            {
                xs.Add(p.x);
            }
        }

        // Secondary: use midpoint x from any known left-right pair.
        TryCollectPairMidX(positions, xs, "outline_02_bottom_right_corner", "outline_06_bottom_left_corner");
        TryCollectPairMidX(positions, xs, "outline_03_top_right_corner", "outline_05_top_left_corner");
        TryCollectPairMidX(positions, xs, "fingerboard_01_bridge_right_side", "fingerboard_04_bridge_left_side");
        TryCollectPairMidX(positions, xs, "fingerboard_02_nut_right_side", "fingerboard_03_nut_left_side");
        TryCollectPairMidX(positions, xs, "outline_02", "outline_06");
        TryCollectPairMidX(positions, xs, "outline_03", "outline_05");
        TryCollectPairMidX(positions, xs, "fingerboard_01", "fingerboard_04");
        TryCollectPairMidX(positions, xs, "fingerboard_02", "fingerboard_03");

        if (xs.Count == 0)
        {
            midX = 0f;
            return false;
        }

        float sum = 0f;
        for (int i = 0; i < xs.Count; i++)
        {
            sum += xs[i];
        }

        midX = sum / xs.Count;
        return true;
    }

    private static void TryCollectPairMidX(
        Dictionary<string, Vector3> positions,
        List<float> xs,
        string keyA,
        string keyB
    )
    {
        if (positions.TryGetValue(keyA, out Vector3 a) && positions.TryGetValue(keyB, out Vector3 b))
        {
            xs.Add((a.x + b.x) * 0.5f);
        }
    }

    private static void DeriveRequiredKeypoints(Dictionary<string, Vector3> positions)
    {
        if (!positions.ContainsKey("center") && TryDeriveCenter(positions, out Vector3 center))
        {
            positions["center"] = center;
        }

        if (!positions.ContainsKey("neck_end") && TryDeriveNeckEnd(positions, out Vector3 neckEnd))
        {
            positions["neck_end"] = neckEnd;
        }

        if (!positions.ContainsKey("body_end") && TryDeriveBodyEnd(positions, out Vector3 bodyEnd))
        {
            positions["body_end"] = bodyEnd;
        }

        if (!positions.ContainsKey("chin_anchor") && TryDeriveChinAnchor(positions, out Vector3 chinAnchor))
        {
            positions["chin_anchor"] = chinAnchor;
        }
    }

    private static bool TryDeriveCenter(Dictionary<string, Vector3> positions, out Vector3 center)
    {
        // Best: bridge midpoint from fingerboard bridge edge.
        if (TryMidpoint(
            positions,
            out center,
            "fingerboard_01_bridge_right_side",
            "fingerboard_04_bridge_left_side"
        ))
        {
            return true;
        }

        // Compatibility fallback for older naming.
        if (TryMidpoint(
            positions,
            out center,
            "fingerboard_01_bridge_treble_side",
            "fingerboard_04_bridge_bass_side"
        ))
        {
            return true;
        }

        // Legacy fallback.
        if (TryMidpoint(positions, out center, "fingerboard_01", "fingerboard_04"))
        {
            return true;
        }

        // Fallback: average of available bridge-side string points.
        List<Vector3> bridgePoints = new List<Vector3>();
        string[] strings = { "G", "D", "A", "E" };
        for (int i = 0; i < strings.Length; i++)
        {
            string s = strings[i];
            if (TryGetAnyPoint(positions, out Vector3 p, "string_" + s + "_bridge_side", "string_" + s + "_1"))
            {
                bridgePoints.Add(p);
            }
        }

        if (bridgePoints.Count >= 2)
        {
            Vector3 sum = Vector3.zero;
            for (int i = 0; i < bridgePoints.Count; i++)
            {
                sum += bridgePoints[i];
            }
            center = sum / bridgePoints.Count;
            return true;
        }

        center = Vector3.zero;
        return false;
    }

    private static bool TryDeriveNeckEnd(Dictionary<string, Vector3> positions, out Vector3 neckEnd)
    {
        // Best: nut midpoint from fingerboard nut edge.
        if (TryMidpoint(
            positions,
            out neckEnd,
            "fingerboard_02_nut_right_side",
            "fingerboard_03_nut_left_side"
        ))
        {
            return true;
        }

        // Compatibility fallback for older naming.
        if (TryMidpoint(
            positions,
            out neckEnd,
            "fingerboard_02_nut_treble_side",
            "fingerboard_03_nut_bass_side"
        ))
        {
            return true;
        }

        // Legacy fallback.
        if (TryMidpoint(positions, out neckEnd, "fingerboard_02", "fingerboard_03"))
        {
            return true;
        }

        // Fallback: average of string fingerboard-end points.
        List<Vector3> nutPoints = new List<Vector3>();
        string[] strings = { "G", "D", "A", "E" };
        for (int i = 0; i < strings.Length; i++)
        {
            string s = strings[i];
            if (TryGetAnyPoint(positions, out Vector3 p, "string_" + s + "_fingerboard_end", "string_" + s + "_2"))
            {
                nutPoints.Add(p);
            }
        }

        if (nutPoints.Count >= 2)
        {
            Vector3 sum = Vector3.zero;
            for (int i = 0; i < nutPoints.Count; i++)
            {
                sum += nutPoints[i];
            }
            neckEnd = sum / nutPoints.Count;
            return true;
        }

        neckEnd = Vector3.zero;
        return false;
    }

    private static bool TryDeriveBodyEnd(Dictionary<string, Vector3> positions, out Vector3 bodyEnd)
    {
        if (TryGetAnyPoint(positions, out bodyEnd, "outline_01_bottom_center", "outline_01"))
        {
            return true;
        }

        if (TryMidpoint(
            positions,
            out bodyEnd,
            "outline_02_bottom_right_corner",
            "outline_06_bottom_left_corner"
        ))
        {
            return true;
        }

        if (TryMidpoint(positions, out bodyEnd, "outline_02", "outline_06"))
        {
            return true;
        }

        bodyEnd = Vector3.zero;
        return false;
    }

    private static bool TryDeriveChinAnchor(Dictionary<string, Vector3> positions, out Vector3 chinAnchor)
    {
        if (TryGetAnyPoint(positions, out chinAnchor, "chin_anchor_hint", "chin_rest_contact"))
        {
            return true;
        }

        if (!TryMidpoint(
            positions,
            out Vector3 topMid,
            "outline_03_top_right_corner",
            "outline_05_top_left_corner"
        ))
        {
            if (!TryMidpoint(positions, out topMid, "outline_03", "outline_05"))
            {
                chinAnchor = Vector3.zero;
                return false;
            }
        }

        if (TryGetAnyPoint(positions, out Vector3 upperMiddle, "outline_04_upper_middle_body_end", "outline_04"))
        {
            // Project backward from upper-middle toward the chin side along the instrument axis.
            chinAnchor = topMid + (topMid - upperMiddle) * 1.6f;
            return true;
        }

        if (TryGetAnyPoint(positions, out Vector3 center, "center") && TryGetAnyPoint(positions, out Vector3 neckEnd, "neck_end"))
        {
            Vector3 axis = (neckEnd - center);
            if (axis.sqrMagnitude > 1e-8f)
            {
                chinAnchor = topMid - axis.normalized * 0.05f;
                return true;
            }
        }

        chinAnchor = Vector3.zero;
        return false;
    }

    private static bool TryMidpoint(
        Dictionary<string, Vector3> positions,
        out Vector3 mid,
        string keyA,
        string keyB
    )
    {
        if (positions.TryGetValue(keyA, out Vector3 a) && positions.TryGetValue(keyB, out Vector3 b))
        {
            mid = (a + b) * 0.5f;
            return true;
        }

        mid = Vector3.zero;
        return false;
    }

    private static bool TryGetAnyPoint(Dictionary<string, Vector3> positions, out Vector3 value, params string[] keys)
    {
        for (int i = 0; i < keys.Length; i++)
        {
            if (positions.TryGetValue(keys[i], out value))
            {
                return true;
            }
        }

        value = Vector3.zero;
        return false;
    }

    public string GetExportAbsolutePath()
    {
        string projectRoot = Directory.GetCurrentDirectory();
        return Path.GetFullPath(Path.Combine(projectRoot, exportRelativePath));
    }

    public bool TryExportToFile(out string message)
    {
        message = string.Empty;
        if (!TryBuildExport(out string json, out string error))
        {
            message = error;
            return false;
        }

        string outputPath = GetExportAbsolutePath();
        string dir = Path.GetDirectoryName(outputPath);
        if (!string.IsNullOrEmpty(dir))
        {
            Directory.CreateDirectory(dir);
        }

        File.WriteAllText(outputPath, json, Encoding.UTF8);
        message = outputPath;
        return true;
    }

    private static string BuildProfileJson(Dictionary<string, Vector3> points)
    {
        string[] stringNames = { "G", "D", "A", "E" };

        List<KeyValuePair<string, Vector3>> outline = CollectPrefixed(points, "outline_");
        List<KeyValuePair<string, Vector3>> fingerboard = CollectPrefixed(points, "fingerboard_");
        bool hasBowContact = points.TryGetValue("bow_contact", out Vector3 bowContact);

        HashSet<string> consumed = new HashSet<string>(StringComparer.Ordinal);
        for (int i = 0; i < RequiredKeys.Length; i++)
        {
            consumed.Add(RequiredKeys[i]);
        }
        // Consume legacy one-point and new two-point string keys.
        for (int i = 0; i < stringNames.Length; i++)
        {
            consumed.Add("string_" + stringNames[i]);
            consumed.Add("string_" + stringNames[i] + "_1");
            consumed.Add("string_" + stringNames[i] + "_2");
            consumed.Add("string_" + stringNames[i] + "_bridge_side");
            consumed.Add("string_" + stringNames[i] + "_fingerboard_end");
        }
        for (int i = 0; i < outline.Count; i++)
        {
            consumed.Add(outline[i].Key);
        }
        for (int i = 0; i < fingerboard.Count; i++)
        {
            consumed.Add(fingerboard[i].Key);
        }
        if (hasBowContact)
        {
            consumed.Add("bow_contact");
        }

        List<KeyValuePair<string, Vector3>> supplementary = new List<KeyValuePair<string, Vector3>>();
        foreach (var kv in points)
        {
            if (!consumed.Contains(kv.Key))
            {
                supplementary.Add(kv);
            }
        }
        supplementary.Sort((a, b) => string.CompareOrdinal(a.Key, b.Key));

        StringBuilder sb = new StringBuilder();
        sb.AppendLine("{");
        sb.AppendLine("  \"profiles\": {");
        sb.AppendLine("    \"violin\": {");
        sb.AppendLine("      \"pnp_keypoints\": {");

        for (int i = 0; i < RequiredKeys.Length; i++)
        {
            string key = RequiredKeys[i];
            Vector3 p = points[key];
            string comma = i == RequiredKeys.Length - 1 ? string.Empty : ",";
            sb.Append("        \"").Append(key).Append("\": [")
              .Append(FloatString(p.x)).Append(", ")
              .Append(FloatString(p.y)).Append(", ")
              .Append(FloatString(p.z)).Append("]")
              .Append(comma)
              .AppendLine();
        }

        sb.AppendLine("      },");
        sb.AppendLine("      \"geometry\": {");

        // Strings block
        sb.AppendLine("        \"strings\": {");
        for (int i = 0; i < stringNames.Length; i++)
        {
            string name = stringNames[i];
            bool hasLegacy = points.TryGetValue("string_" + name, out Vector3 legacyPoint);
            bool hasP1 = points.TryGetValue("string_" + name + "_1", out Vector3 p1);
            bool hasP2 = points.TryGetValue("string_" + name + "_2", out Vector3 p2);
            bool hasBridgeSide = points.TryGetValue("string_" + name + "_bridge_side", out Vector3 bridgeSidePoint);
            bool hasFingerboardEnd = points.TryGetValue("string_" + name + "_fingerboard_end", out Vector3 fingerboardEndPoint);

            if (!hasP1 && !hasP2 && hasBridgeSide && hasFingerboardEnd)
            {
                p1 = bridgeSidePoint;
                p2 = fingerboardEndPoint;
                hasP1 = true;
                hasP2 = true;
            }

            if (!hasLegacy && !(hasP1 && hasP2))
            {
                continue;
            }

            bool hasLater = false;
            for (int j = i + 1; j < stringNames.Length; j++)
            {
                string later = stringNames[j];
                if (points.ContainsKey("string_" + later) ||
                    (points.ContainsKey("string_" + later + "_1") && points.ContainsKey("string_" + later + "_2")) ||
                    (points.ContainsKey("string_" + later + "_bridge_side") && points.ContainsKey("string_" + later + "_fingerboard_end")))
                {
                    hasLater = true;
                    break;
                }
            }
            string comma = hasLater ? "," : string.Empty;

            if (hasP1 && hasP2)
            {
                sb.Append("          \"").Append(name).Append("\": [[")
                  .Append(FloatString(p1.x)).Append(", ")
                  .Append(FloatString(p1.y)).Append(", ")
                  .Append(FloatString(p1.z)).Append("], [")
                  .Append(FloatString(p2.x)).Append(", ")
                  .Append(FloatString(p2.y)).Append(", ")
                  .Append(FloatString(p2.z)).Append("]]")
                  .Append(comma)
                  .AppendLine();
            }
            else
            {
                sb.Append("          \"").Append(name).Append("\": [")
                  .Append(FloatString(legacyPoint.x)).Append(", ")
                  .Append(FloatString(legacyPoint.y)).Append(", ")
                  .Append(FloatString(legacyPoint.z)).Append("]")
                  .Append(comma)
                  .AppendLine();
            }
        }
        sb.AppendLine("        },");

        // Body outline block
        sb.AppendLine("        \"body_outline\": [");
        for (int i = 0; i < outline.Count; i++)
        {
            Vector3 p = outline[i].Value;
            string comma = i == outline.Count - 1 ? string.Empty : ",";
            sb.Append("          [")
              .Append(FloatString(p.x)).Append(", ")
              .Append(FloatString(p.y)).Append(", ")
              .Append(FloatString(p.z)).Append("]")
              .Append(comma)
              .AppendLine();
        }
        sb.AppendLine("        ],");

        // Fingerboard block
        sb.AppendLine("        \"fingerboard\": [");
        for (int i = 0; i < fingerboard.Count; i++)
        {
            Vector3 p = fingerboard[i].Value;
            string comma = i == fingerboard.Count - 1 ? string.Empty : ",";
            sb.Append("          [")
              .Append(FloatString(p.x)).Append(", ")
              .Append(FloatString(p.y)).Append(", ")
              .Append(FloatString(p.z)).Append("]")
              .Append(comma)
              .AppendLine();
        }
        sb.AppendLine("        ],");

        // Bow contact block
        sb.Append("        \"bow_contact\": ");
        if (hasBowContact)
        {
            sb.Append("[")
              .Append(FloatString(bowContact.x)).Append(", ")
              .Append(FloatString(bowContact.y)).Append(", ")
              .Append(FloatString(bowContact.z)).Append("]")
              .AppendLine(",");
        }
        else
        {
            sb.AppendLine("null,");
        }

        // Supplementary keypoints (not used by PnP)
        sb.AppendLine("        \"supplementary_keypoints\": {");
        for (int i = 0; i < supplementary.Count; i++)
        {
            var kv = supplementary[i];
            string comma = i == supplementary.Count - 1 ? string.Empty : ",";
            sb.Append("          \"").Append(kv.Key).Append("\": [")
              .Append(FloatString(kv.Value.x)).Append(", ")
              .Append(FloatString(kv.Value.y)).Append(", ")
              .Append(FloatString(kv.Value.z)).Append("]")
              .Append(comma)
              .AppendLine();
        }
        sb.AppendLine("        }");
        sb.AppendLine("      }");
        sb.AppendLine("    }");
        sb.AppendLine("  }");
        sb.AppendLine("}");
        return sb.ToString();
    }

    private static void TryAssignNamedPoint(
        Dictionary<string, Vector3> points,
        Dictionary<string, Vector3> outDict,
        string key
    )
    {
        if (points.TryGetValue(key, out Vector3 value))
        {
            outDict[key] = value;
        }
    }

    private static List<KeyValuePair<string, Vector3>> CollectPrefixed(
        Dictionary<string, Vector3> points,
        string prefix
    )
    {
        List<KeyValuePair<string, Vector3>> list = new List<KeyValuePair<string, Vector3>>();
        foreach (var kv in points)
        {
            if (kv.Key.StartsWith(prefix, StringComparison.Ordinal))
            {
                list.Add(kv);
            }
        }
        list.Sort((a, b) => string.CompareOrdinal(a.Key, b.Key));
        return list;
    }

    private static string FloatString(float value)
    {
        return value.ToString("0.######", CultureInfo.InvariantCulture);
    }

    private void OnDrawGizmos()
    {
        if (keypoints == null)
        {
            return;
        }

        Dictionary<string, Vector3> positions = new Dictionary<string, Vector3>(StringComparer.Ordinal);
        HashSet<string> sceneKeys = new HashSet<string>(StringComparer.Ordinal);
        for (int i = 0; i < keypoints.Count; i++)
        {
            KeypointBinding binding = keypoints[i];
            if (binding == null || string.IsNullOrWhiteSpace(binding.key) || binding.marker == null)
            {
                continue;
            }

            string key = binding.key.Trim();
            sceneKeys.Add(key);
            positions[key] = RootOrSelf.InverseTransformPoint(binding.marker.position);
        }

        Dictionary<string, Vector3> mirroredVirtual = new Dictionary<string, Vector3>(positions, StringComparer.Ordinal);
        DeriveMirroredSupplementaryKeypoints(mirroredVirtual, useFixedMirrorCenterX, fixedMirrorCenterX);

        Gizmos.color = new Color(1f, 0.8f, 0f, 0.9f);
        for (int i = 0; i < keypoints.Count; i++)
        {
            KeypointBinding binding = keypoints[i];
            if (binding == null || binding.marker == null)
            {
                continue;
            }

            Gizmos.DrawSphere(binding.marker.position, gizmoSize);
        }

        // Draw virtual mirrored points (not scene objects).
        Gizmos.color = new Color(0.2f, 0.95f, 1f, 0.95f);
        string[] mirroredLeftKeys =
        {
            "outline_05_top_left_corner",
            "outline_06_bottom_left_corner",
            "fingerboard_03_nut_left_side",
            "fingerboard_04_bridge_left_side",
            "outline_05",
            "outline_06",
            "fingerboard_03",
            "fingerboard_04",
            "fingerboard_03_nut_bass_side",
            "fingerboard_04_bridge_bass_side",
        };

        for (int i = 0; i < mirroredLeftKeys.Length; i++)
        {
            string key = mirroredLeftKeys[i];
            if (sceneKeys.Contains(key))
            {
                continue;
            }
            if (!mirroredVirtual.TryGetValue(key, out Vector3 local))
            {
                continue;
            }

            Vector3 world = RootOrSelf.TransformPoint(local);
            Gizmos.DrawWireSphere(world, gizmoSize * 1.2f);
            Gizmos.DrawLine(world + Vector3.left * gizmoSize, world + Vector3.right * gizmoSize);
            Gizmos.DrawLine(world + Vector3.forward * gizmoSize, world + Vector3.back * gizmoSize);
        }
    }
}
