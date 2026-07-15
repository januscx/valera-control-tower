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
        private static readonly System.Globalization.CultureInfo _invariant =
            System.Globalization.CultureInfo.InvariantCulture;

        public string kind;
        public bool deadman;
        public Dictionary<string, float> jointVelocity = new Dictionary<string, float>();

        public string ToJson()
        {
            var sb = new StringBuilder();
            sb.Append("{\"kind\":\"");
            sb.Append(kind ?? "");
            sb.Append("\",\"deadman\":");
            sb.Append(deadman ? "true" : "false");
            sb.Append(",\"joint_velocity\":{");
            bool first = true;
            foreach (var kv in jointVelocity)
            {
                if (kv.Key == null) continue;
                float value = kv.Value;
                if (float.IsNaN(value) || float.IsInfinity(value)) continue;

                if (!first) sb.Append(",");
                first = false;
                sb.Append('"');
                sb.Append(EscapeJsonString(kv.Key));
                sb.Append("\":");
                sb.Append(value.ToString("0.0########", _invariant));
            }
            sb.Append("}}");
            return sb.ToString();
        }

        private static string EscapeJsonString(string raw)
        {
            if (raw == null) return "";
            var sb = new StringBuilder(raw.Length);
            foreach (char c in raw)
            {
                switch (c)
                {
                    case '"':  sb.Append("\\\""); break;
                    case '\\': sb.Append("\\\\"); break;
                    case '\n': sb.Append("\\n");  break;
                    case '\r': sb.Append("\\r");  break;
                    case '\t': sb.Append("\\t");  break;
                    default:
                        if (c < 0x20)
                            sb.AppendFormat(_invariant, "\\u{0:X4}", (int)c);
                        else
                            sb.Append(c);
                        break;
                }
            }
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
