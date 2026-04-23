using System;
using System.Collections.Generic;
using UnityEngine;

[ExecuteAlways]
public class ViolinFingeringCalculator : MonoBehaviour
{
	[Serializable]
	public struct FingeringPoint
	{
		public int halfStep;
		public float distanceFromFingerboardEnd;
		public Vector3 localPosition;
		public Vector3 worldPosition;
	}

	[Header("References")]
	public ViolinKeypointRig keypointRig;

	[Header("Fingering")]
	[Tooltip("When true, use this fixed string length L for all strings.")]
	public bool useFixedStringLength = true;
	[Tooltip("L in meters. Default 0.328 for violin.")]
	public float fixedStringLength = 0.328f;
	[Tooltip("Number of half-step positions to evaluate, starting at x=0 (open string).")]
	[Min(1)]
	public int halfStepCount = 8;

	[Header("Gizmos")]
	public bool drawFingeringGizmos = true;
	public float pointGizmoRadius = 0.0035f;
	public bool drawConnectingLines = true;

	private static readonly string[] StringNames = { "G", "D", "A", "E" };
	private const float RatioPerHalfStep = 0.943874312682f; // Pow(0.5, 1/12)

	private void OnValidate()
	{
		if (keypointRig == null)
		{
			keypointRig = GetComponent<ViolinKeypointRig>();
		}

		fixedStringLength = Mathf.Max(0.0001f, fixedStringLength);
		halfStepCount = Mathf.Max(1, halfStepCount);
		pointGizmoRadius = Mathf.Max(0.0001f, pointGizmoRadius);
	}

	public FingeringPoint[] GetFingeringForString(string stringName)
	{
		return GetFingeringForString(stringName, halfStepCount);
	}

	public FingeringPoint[] GetFingeringForString(string stringName, int count)
	{
		if (string.IsNullOrWhiteSpace(stringName) || count <= 0)
		{
			return Array.Empty<FingeringPoint>();
		}

		if (!TryGetStringEndpoints(stringName.Trim().ToUpperInvariant(), out Vector3 bridgeSide, out Vector3 fingerboardEnd))
		{
			return Array.Empty<FingeringPoint>();
		}

		Vector3 direction = bridgeSide - fingerboardEnd;
		float measuredLength = direction.magnitude;
		if (measuredLength <= 1e-6f)
		{
			return Array.Empty<FingeringPoint>();
		}

		direction /= measuredLength;
		float length = useFixedStringLength ? fixedStringLength : measuredLength;

		FingeringPoint[] points = new FingeringPoint[count];
		for (int x = 0; x < count; x++)
		{
			float d = DistanceFromFingerboardEnd(x, length);
			Vector3 local = fingerboardEnd + direction * d;
			points[x] = new FingeringPoint
			{
				halfStep = x,
				distanceFromFingerboardEnd = d,
				localPosition = local,
				worldPosition = keypointRig.RootOrSelf.TransformPoint(local),
			};
		}

		return points;
	}

	public Vector3[] GetWorldPositionsForString(string stringName, int count)
	{
		FingeringPoint[] points = GetFingeringForString(stringName, count);
		Vector3[] result = new Vector3[points.Length];
		for (int i = 0; i < points.Length; i++)
		{
			result[i] = points[i].worldPosition;
		}

		return result;
	}

	private float DistanceFromFingerboardEnd(int halfStep, float stringLength)
	{
		// D(x) = L - L * ((0.5)^(1/12))^x
		return stringLength - (stringLength * Mathf.Pow(RatioPerHalfStep, halfStep));
	}

	private bool TryGetStringEndpoints(string stringName, out Vector3 bridgeSide, out Vector3 fingerboardEnd)
	{
		bridgeSide = Vector3.zero;
		fingerboardEnd = Vector3.zero;

		if (keypointRig == null)
		{
			return false;
		}

		Dictionary<string, Vector3> localPoints = BuildLocalPointMap();
		string bridgeKey = "string_" + stringName + "_bridge_side";
		string fingerboardKey = "string_" + stringName + "_fingerboard_end";

		bool hasBridge = localPoints.TryGetValue(bridgeKey, out bridgeSide);
		bool hasFingerboard = localPoints.TryGetValue(fingerboardKey, out fingerboardEnd);
		if (hasBridge && hasFingerboard)
		{
			return true;
		}

		if (TryGetMirrorSource(stringName, out string sourceString))
		{
			string sourceBridgeKey = "string_" + sourceString + "_bridge_side";
			string sourceFingerboardKey = "string_" + sourceString + "_fingerboard_end";

			if (localPoints.TryGetValue(sourceBridgeKey, out Vector3 sourceBridge)
				&& localPoints.TryGetValue(sourceFingerboardKey, out Vector3 sourceFingerboard)
				&& TryGetMirrorCenterX(localPoints, out float centerX))
			{
				bridgeSide = MirrorAcrossX(sourceBridge, centerX);
				fingerboardEnd = MirrorAcrossX(sourceFingerboard, centerX);
				return true;
			}
		}

		return false;
	}

	private Dictionary<string, Vector3> BuildLocalPointMap()
	{
		Dictionary<string, Vector3> local = new Dictionary<string, Vector3>(StringComparer.Ordinal);
		Transform root = keypointRig.RootOrSelf;

		for (int i = 0; i < keypointRig.keypoints.Count; i++)
		{
			ViolinKeypointRig.KeypointBinding binding = keypointRig.keypoints[i];
			if (binding == null || string.IsNullOrWhiteSpace(binding.key) || binding.marker == null)
			{
				continue;
			}

			local[binding.key.Trim()] = root.InverseTransformPoint(binding.marker.position);
		}

		return local;
	}

	private bool TryGetMirrorCenterX(Dictionary<string, Vector3> localPoints, out float centerX)
	{
		if (keypointRig.useFixedMirrorCenterX)
		{
			centerX = keypointRig.fixedMirrorCenterX;
			return true;
		}

		List<float> xValues = new List<float>();
		CollectX(localPoints, xValues, "center");
		CollectX(localPoints, xValues, "neck_end");
		CollectX(localPoints, xValues, "outline_01_bottom_center");
		CollectX(localPoints, xValues, "outline_04_upper_middle_body_end");

		if (localPoints.TryGetValue("outline_02_bottom_right_corner", out Vector3 right)
			&& localPoints.TryGetValue("outline_06_bottom_left_corner", out Vector3 left))
		{
			xValues.Add((right.x + left.x) * 0.5f);
		}

		if (xValues.Count == 0)
		{
			centerX = 0f;
			return false;
		}

		float sum = 0f;
		for (int i = 0; i < xValues.Count; i++)
		{
			sum += xValues[i];
		}

		centerX = sum / xValues.Count;
		return true;
	}

	private static void CollectX(Dictionary<string, Vector3> points, List<float> values, string key)
	{
		if (points.TryGetValue(key, out Vector3 p))
		{
			values.Add(p.x);
		}
	}

	private static bool TryGetMirrorSource(string stringName, out string sourceString)
	{
		sourceString = string.Empty;
		if (string.Equals(stringName, "D", StringComparison.Ordinal))
		{
			sourceString = "A";
			return true;
		}

		if (string.Equals(stringName, "G", StringComparison.Ordinal))
		{
			sourceString = "E";
			return true;
		}

		return false;
	}

	private static Vector3 MirrorAcrossX(Vector3 local, float centerX)
	{
		return new Vector3(2f * centerX - local.x, local.y, local.z);
	}

	private void OnDrawGizmos()
	{
		if (!drawFingeringGizmos || keypointRig == null)
		{
			return;
		}

		for (int i = 0; i < StringNames.Length; i++)
		{
			FingeringPoint[] points = GetFingeringForString(StringNames[i], halfStepCount);
			if (points.Length == 0)
			{
				continue;
			}

			Gizmos.color = GetStringColor(StringNames[i]);
			for (int p = 0; p < points.Length; p++)
			{
				Gizmos.DrawSphere(points[p].worldPosition, pointGizmoRadius);

				if (drawConnectingLines && p > 0)
				{
					Gizmos.DrawLine(points[p - 1].worldPosition, points[p].worldPosition);
				}
			}
		}
	}

	private static Color GetStringColor(string stringName)
	{
		if (string.Equals(stringName, "G", StringComparison.Ordinal))
		{
			return new Color(0.25f, 0.8f, 0.35f, 0.95f);
		}

		if (string.Equals(stringName, "D", StringComparison.Ordinal))
		{
			return new Color(0.95f, 0.85f, 0.25f, 0.95f);
		}

		if (string.Equals(stringName, "A", StringComparison.Ordinal))
		{
			return new Color(1f, 0.55f, 0.2f, 0.95f);
		}

		return new Color(0.95f, 0.2f, 0.2f, 0.95f);
	}
}
