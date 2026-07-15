using System;

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

    [Serializable]
    public sealed class ArmJogPayload
    {
        public string kind;
        public bool deadman;
        public string joint_velocity;
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
