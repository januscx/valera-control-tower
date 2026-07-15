using System;
using System.Collections.Generic;
using System.Text;

namespace Valera.QuestHeadClient.Transport
{
    public enum ControlMode
    {
        HEAD_ONLY,
        DRIVE,
        ARM,
    }

    public enum ModeTransition
    {
        NONE,
        STOPPING_BASE,
        STOPPING_ARM,
    }

    public enum GatewayState
    {
        IDLE,
        AWAITING_RECENTER,
        ACTIVE,
        SAFE_STOPPED,
        ESTOP_LATCHED,
    }

    [Serializable]
    public sealed class BaseDrivePayload
    {
        public float throttle;
        public float steering;
        public bool deadman;
    }

    public sealed class ArmJogPayload
    {
        public string kind;
        public bool deadman;
        public Dictionary<string, float> jointVelocity = new Dictionary<string, float>();

        public string ToJson()
        {
            var sb = new StringBuilder();
            sb.Append("{\"kind\":\"");
            sb.Append(kind);
            sb.Append("\",\"deadman\":");
            sb.Append(deadman ? "true" : "false");
            sb.Append(",\"joint_velocity\":{");
            bool first = true;
            foreach (var kv in jointVelocity)
            {
                if (!first) sb.Append(",");
                first = false;
                sb.Append('"');
                sb.Append(kv.Key);
                sb.Append("\":");
                sb.Append(kv.Value.ToString("0.0########", System.Globalization.CultureInfo.InvariantCulture));
            }
            sb.Append("}}");
            return sb.ToString();
        }
    }

    [Serializable]
    public sealed class GatewayStateData
    {
        public string state;
        public string current_mode;
        public string requested_mode;
        public string transition;
    }
}
