using UnityEngine;
using UnityEngine.UI;
using Valera.QuestHeadClient.State;
using Valera.QuestHeadClient.Transport;

namespace Valera.QuestHeadClient.UI
{
    public sealed class GatewayStatusHud : MonoBehaviour
    {
        [SerializeField] private GatewayStateStore _store;
        [SerializeField] private Text _statusText;

        private void Awake()
        {
            BuildDefaultIfNeeded();
        }

        private void Update()
        {
            if (_store == null || _statusText == null) return;
            _statusText.text = FormatStatus();
        }

        private string FormatStatus()
        {
            if (_store.State == GatewayState.ESTOP_LATCHED)
                return "ESTOP_LATCHED";

            string status = $"{_store.State} / {_store.CurrentMode}";

            bool hasTransition = _store.Transition != ModeTransition.NONE;
            bool hasRequested = !string.IsNullOrEmpty(_store.RequestedMode);

            if (hasRequested && hasTransition)
                status += $" → {_store.RequestedMode} / {_store.Transition}";

            if (!string.IsNullOrEmpty(_store.LastRejection))
                status += $"\nLast: {_store.LastRejection}";

            return status;
        }

        private void BuildDefaultIfNeeded()
        {
            if (_statusText != null) return;

            GameObject canvasObject = new GameObject("GatewayStatusCanvas");
            canvasObject.transform.SetParent(transform, false);
            Canvas canvas = canvasObject.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.WorldSpace;
            canvasObject.AddComponent<CanvasScaler>();
            canvasObject.AddComponent<GraphicRaycaster>();

            GameObject textObject = new GameObject("Status");
            textObject.transform.SetParent(canvasObject.transform, false);
            _statusText = textObject.AddComponent<Text>();
            _statusText.font = Resources.GetBuiltinResource<Font>("Arial.ttf");
            _statusText.fontSize = 28;
            _statusText.color = Color.white;
            RectTransform textRect = _statusText.rectTransform;
            textRect.sizeDelta = new Vector2(900, 300);
        }
    }
}
