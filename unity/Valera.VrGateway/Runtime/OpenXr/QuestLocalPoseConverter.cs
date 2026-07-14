using System;
using UnityEngine;
using Valera.VrGateway.Json;

namespace Valera.VrGateway.OpenXr
{
    public static class QuestLocalPoseConverter
    {
        public static Quaternion Convert(Quaternion unityOrientation)
        {
            float squared = unityOrientation.x * unityOrientation.x
                + unityOrientation.y * unityOrientation.y
                + unityOrientation.z * unityOrientation.z
                + unityOrientation.w * unityOrientation.w;
            if (!float.IsFinite(squared) || squared <= 1e-24f)
            {
                throw new WireValidationException("Unity orientation must be finite and non-zero.");
            }

            float inverseLength = 1f / Mathf.Sqrt(squared);
            Quaternion normalized = new Quaternion(
                unityOrientation.x * inverseLength,
                unityOrientation.y * inverseLength,
                unityOrientation.z * inverseLength,
                unityOrientation.w * inverseLength);
            return new Quaternion(-normalized.x, -normalized.y, normalized.z, normalized.w);
        }
    }
}
