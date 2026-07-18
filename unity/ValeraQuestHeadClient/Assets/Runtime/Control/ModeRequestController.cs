using System;
using System.Diagnostics;
using UnityEngine;
using Valera.QuestHeadClient.Input;
using Valera.QuestHeadClient.State;
using Valera.QuestHeadClient.Transport;

namespace Valera.QuestHeadClient.Control
{
    public sealed class ModeRequestController : MonoBehaviour
    {
        private readonly LongPressDetector _longPress = new LongPressDetector();

        [SerializeField] private QuestControllerInput _input;
        [SerializeField] private VrGatewayWebSocket _ws;
        [SerializeField] private GatewayStateStore _store;
        [SerializeField] private string _sessionId;

        private int _nextSequence;

        private void Awake()
        {
            _input = _input ?? GetComponent<QuestControllerInput>();
            _longPress.OnLongPress += OnLongPress;
        }

        public void SetSessionId(string sessionId)
        {
            _sessionId = sessionId;
        }

        private void Update()
        {
            _longPress.Update(_input.ButtonA, Time.deltaTime);
        }

        private void OnLongPress()
        {
            string targetMode = _store.CurrentMode switch
            {
                ControlMode.HEAD_ONLY => "drive",
                ControlMode.DRIVE => "arm",
                ControlMode.ARM => "drive",
                _ => "head_only",
            };
            SendModeSet(targetMode);
        }

        private void SendModeSet(string mode)
        {
            if (_ws == null || !_ws.IsConnected) return;

            var envelope = new ModeCommandEnvelope
            {
                session_id = _sessionId,
                sequence = _nextSequence++,
                timestamp_ms = MonotonicMilliseconds(),
                payload = new ModeSetPayload { mode = mode },
            };

            _ = SendJson(JsonUtility.ToJson(envelope));
        }

        private async System.Threading.Tasks.Task SendJson(string json)
        {
            try
            {
                await _ws.SendCommand(json);
            }
            catch
            {
            }
        }

        private static long MonotonicMilliseconds()
        {
            return Stopwatch.GetTimestamp() * 1000L / Stopwatch.Frequency;
        }

        [Serializable]
        private sealed class ModeCommandEnvelope
        {
            public string schema_version = "0.1";
            public string command = "mode.set";
            public string session_id;
            public int sequence;
            public long timestamp_ms;
            public ModeSetPayload payload;
        }

        [Serializable]
        private sealed class ModeSetPayload
        {
            public string mode;
        }
    }
}
