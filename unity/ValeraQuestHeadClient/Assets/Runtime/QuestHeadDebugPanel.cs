using UnityEngine;
using UnityEngine.Events;
using UnityEngine.UI;

namespace Valera.QuestHeadClient
{
    public sealed class QuestHeadDebugPanel : MonoBehaviour
    {
        // Button labels are intentionally explicit for the minimal world-space panel.
        private const string ConnectLabel = "Connect";
        private const string DisconnectLabel = "Disconnect";
        private const string RecenterLabel = "Recenter";
        [SerializeField] private Text statusText;
        [SerializeField] private Button connectButton;
        [SerializeField] private Button disconnectButton;
        [SerializeField] private Button recenterButton;

        private string socketState = "Disconnected";
        private string gatewayState = "IDLE";
        private string sessionId = "-";
        private int txCount;
        private int rxCount;
        private string neckTarget = "-";
        private string lastError = "-";

        public void SetHandlers(UnityAction connect, UnityAction disconnect, UnityAction recenter)
        {
            connectButton?.onClick.AddListener(connect);
            disconnectButton?.onClick.AddListener(disconnect);
            recenterButton?.onClick.AddListener(recenter);
        }

        public void SetSocketState(string value) { socketState = value; Refresh(); }
        public void SetGatewayState(string value) { gatewayState = value; Refresh(); }
        public void SetSession(string value) { sessionId = value ?? "-"; Refresh(); }
        public void SetCounters(int tx, int rx) { txCount = tx; rxCount = rx; Refresh(); }
        public void SetNeckTarget(double pan, double tilt, long sequence) { neckTarget = $"pan={pan:F2}, tilt={tilt:F2}, seq={sequence}"; Refresh(); }
        public void SetError(string value) { lastError = string.IsNullOrEmpty(value) ? "-" : value; Refresh(); }

        private void Awake()
        {
            BuildDefaultPanelIfNeeded();
            Refresh();
        }

        private void BuildDefaultPanelIfNeeded()
        {
            if (statusText != null && connectButton != null && disconnectButton != null && recenterButton != null) return;

            GameObject canvasObject = new GameObject("QuestHeadDebugCanvas");
            canvasObject.transform.SetParent(transform, false);
            Canvas canvas = canvasObject.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.WorldSpace;
            canvasObject.AddComponent<CanvasScaler>();
            canvasObject.AddComponent<GraphicRaycaster>();

            GameObject textObject = new GameObject("Status");
            textObject.transform.SetParent(canvasObject.transform, false);
            statusText = textObject.AddComponent<Text>();
            statusText.font = Resources.GetBuiltinResource<Font>("Arial.ttf");
            statusText.fontSize = 28;
            statusText.color = Color.white;
            RectTransform textRect = statusText.rectTransform;
            textRect.sizeDelta = new Vector2(900, 300);

            connectButton = CreateButton(canvasObject.transform, ConnectLabel, new Vector2(0, -180));
            disconnectButton = CreateButton(canvasObject.transform, DisconnectLabel, new Vector2(220, -180));
            recenterButton = CreateButton(canvasObject.transform, RecenterLabel, new Vector2(440, -180));
        }

        private static Button CreateButton(Transform parent, string label, Vector2 position)
        {
            GameObject buttonObject = new GameObject(label);
            buttonObject.transform.SetParent(parent, false);
            RectTransform rect = buttonObject.AddComponent<RectTransform>();
            rect.sizeDelta = new Vector2(200, 70);
            rect.anchoredPosition = position;
            Button button = buttonObject.AddComponent<Button>();
            GameObject labelObject = new GameObject("Label");
            labelObject.transform.SetParent(buttonObject.transform, false);
            Text text = labelObject.AddComponent<Text>();
            text.text = label;
            text.alignment = TextAnchor.MiddleCenter;
            text.font = Resources.GetBuiltinResource<Font>("Arial.ttf");
            text.color = Color.black;
            text.rectTransform.anchorMin = Vector2.zero;
            text.rectTransform.anchorMax = Vector2.one;
            text.rectTransform.offsetMin = Vector2.zero;
            text.rectTransform.offsetMax = Vector2.zero;
            return button;
        }

        private void Refresh()
        {
            if (statusText == null) return;
            statusText.text = $"Socket: {socketState}\nGateway: {gatewayState}\nSession: {sessionId}\nTX: {txCount}  RX: {rxCount}\nNeck: {neckTarget}\nError: {lastError}";
        }
    }
}
