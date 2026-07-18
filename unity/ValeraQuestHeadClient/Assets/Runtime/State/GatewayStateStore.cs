using System;
using UnityEngine;
using Valera.QuestHeadClient.Transport;

namespace Valera.QuestHeadClient.State
{
    public sealed class GatewayStateStore
    {
        public GatewayState State { get; private set; }
        public ControlMode CurrentMode { get; private set; }
        public string RequestedMode { get; private set; }
        public ModeTransition Transition { get; private set; }
        public string LastRejection { get; private set; }

        private const string GatewayStateEvent = "gateway.state";
        private const string CommandRejectedEvent = "command.rejected";

        public void UpdateFromEvent(string eventType, string json)
        {
            if (string.IsNullOrEmpty(eventType) || string.IsNullOrEmpty(json)) return;

            switch (eventType)
            {
                case GatewayStateEvent:
                    UpdateGatewayState(json);
                    break;
                case CommandRejectedEvent:
                    UpdateRejection(json);
                    break;
            }
        }

        private void UpdateGatewayState(string json)
        {
            try
            {
                var data = JsonUtility.FromJson<GatewayStateEventData>(json);
                if (data == null) return;

                if (!string.IsNullOrEmpty(data.state))
                    State = ParseEnum(data.state, GatewayState.IDLE);
                if (!string.IsNullOrEmpty(data.current_mode))
                    CurrentMode = ParseEnum(data.current_mode, ControlMode.HEAD_ONLY);
                RequestedMode = data.requested_mode;
                if (!string.IsNullOrEmpty(data.transition))
                    Transition = ParseEnum(data.transition, ModeTransition.NONE);
            }
            catch
            {
            }
        }

        private void UpdateRejection(string json)
        {
            try
            {
                var data = JsonUtility.FromJson<RejectionEventData>(json);
                if (data != null && !string.IsNullOrEmpty(data.message))
                    LastRejection = $"{data.code}: {data.message}";
            }
            catch
            {
            }
        }

        private static T ParseEnum<T>(string value, T defaultValue) where T : struct
        {
            if (Enum.TryParse<T>(value, true, out T result))
                return result;
            return defaultValue;
        }

        [Serializable]
        private sealed class GatewayStateEventData
        {
            public string state;
            public string current_mode;
            public string requested_mode;
            public string transition;
        }

        [Serializable]
        private sealed class RejectionEventData
        {
            public string code;
            public string message;
        }
    }
}
