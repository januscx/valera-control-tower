using System;
using System.Diagnostics;
using UnityEngine;
using Valera.QuestHeadClient.Input;
using Valera.QuestHeadClient.State;
using Valera.QuestHeadClient.Transport;

namespace Valera.QuestHeadClient.Control
{
    public sealed class DriveCommandController : MonoBehaviour
    {
        [SerializeField] private QuestControllerInput _input;
        [SerializeField] private VrGatewayWebSocket _ws;
        [SerializeField] private GatewayStateStore _store;
        [SerializeField] private string _sessionId;

        private int _nextSequence;

        private void Awake()
        {
            _input = _input ?? GetComponent<QuestControllerInput>();
        }

        public void SetSessionId(string sessionId)
        {
            _sessionId = sessionId;
        }

        private void Update()
        {
            bool deadman = _input.LeftGrip > 0.5f;
            if (!deadman || _store.CurrentMode != ControlMode.DRIVE)
            {
                SendBaseDrive(0f, 0f, false);
                return;
            }

            float throttle = Mathf.Clamp(-_input.LeftStick.y, -1f, 1f);
            float steering = Mathf.Clamp(_input.LeftStick.x, -1f, 1f);
            SendBaseDrive(throttle, steering, true);
        }

        private void SendBaseDrive(float throttle, float steering, bool deadman)
        {
            if (_ws == null || !_ws.IsConnected) return;

            var envelope = new DriveCommandEnvelope
            {
                session_id = _sessionId,
                sequence = _nextSequence++,
                timestamp_ms = MonotonicMilliseconds(),
                payload = new BaseDrivePayload
                {
                    throttle = throttle,
                    steering = steering,
                    deadman = deadman,
                },
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
        private sealed class DriveCommandEnvelope
        {
            public string schema_version = "0.1";
            public string command = "base.drive";
            public string session_id;
            public int sequence;
            public long timestamp_ms;
            public BaseDrivePayload payload;
        }
    }
}
