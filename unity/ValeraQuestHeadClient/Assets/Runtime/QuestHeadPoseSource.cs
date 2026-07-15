using UnityEngine;
using Valera.VrGateway.Contracts;
using Valera.VrGateway.OpenXr;

namespace Valera.QuestHeadClient
{
    public sealed class QuestHeadPoseSource : MonoBehaviour
    {
        [SerializeField] private Transform hmdTransform;
        [SerializeField] private bool useEditorFallback = true;
        [SerializeField] private Quaternion editorFallbackOrientation = Quaternion.identity;

        public bool TryGetUnityOrientation(out Quaternion orientation)
        {
            if (hmdTransform == null && Camera.main != null) hmdTransform = Camera.main.transform;
            if (hmdTransform != null)
            {
                orientation = hmdTransform.localRotation;
                return true;
            }

#if UNITY_EDITOR
            if (useEditorFallback)
            {
                orientation = editorFallbackOrientation;
                return true;
            }
#endif
            orientation = Quaternion.identity;
            return false;
        }

        public bool TryGetContractOrientation(out QuaternionDto orientation)
        {
            if (!TryGetUnityOrientation(out Quaternion unityOrientation))
            {
                orientation = null;
                return false;
            }

            Quaternion converted = QuestLocalPoseConverter.Convert(unityOrientation);
            orientation = new QuaternionDto { x = converted.x, y = converted.y, z = converted.z, w = converted.w };
            return true;
        }
    }
}
