using System;
using System.Diagnostics;
using Valera.VrGateway.Contracts;
using Valera.VrGateway.Json;
using Valera.VrGateway.OpenXr;
using Valera.VrGateway.Session;
using UnityEngine;

namespace Valera.QuestHeadClient.Session
{
    public enum QuestHeadClientState
    {
        Disconnected,
        Connecting,
        AwaitingRecenter,
        HeadActive,
        SafeStopped,
    }

    public sealed class QuestHeadSession
    {
        private const long PoseIntervalMilliseconds = 1000 / 20;
        private readonly Func<long> monotonicMilliseconds;
        private readonly Func<string> createSessionId;
        private SessionSequence sequence;
        private long lastTimestampMs = -1;
        private long nextPoseDeadlineMs;
        private bool sessionConfirmed;

        public QuestHeadSession(Func<long> monotonicMilliseconds = null, Func<string> createSessionId = null)
        {
            this.monotonicMilliseconds = monotonicMilliseconds ?? StopwatchMilliseconds;
            this.createSessionId = createSessionId ?? (() => Guid.NewGuid().ToString("N"));
            State = QuestHeadClientState.Disconnected;
        }

        public QuestHeadClientState State { get; private set; }
        public string SessionId { get; private set; }
        public string LastError { get; private set; }
        public bool CanRecenter => State == QuestHeadClientState.AwaitingRecenter;
        public bool CanSendPose => State == QuestHeadClientState.HeadActive && sessionConfirmed;
        public bool SessionConfirmed => sessionConfirmed;

        public string StartSession()
        {
            if (State != QuestHeadClientState.Disconnected) throw new InvalidOperationException("Session is already active.");
            SessionId = createSessionId();
            sequence = new SessionSequence(0);
            State = QuestHeadClientState.Connecting;
            sessionConfirmed = false;
            LastError = null;
            return Encode(new SessionStartCommandDto
            {
                schema_version = WireValues.SchemaVersion,
                command = WireValues.SessionStart,
                session_id = SessionId,
                sequence = sequence.Next(),
                timestamp_ms = NextTimestamp(),
                payload = new SessionStartPayloadDto { requested_mode = "head" },
            });
        }

        public string BuildRecenter(Quaternion unityOrientation)
        {
            if (!CanRecenter) throw new InvalidOperationException("Recenter requires AWAITING_RECENTER.");
            QuaternionDto orientation = ToDto(QuestLocalPoseConverter.Convert(unityOrientation));
            return Encode(new HeadRecenterCommandDto
            {
                schema_version = WireValues.SchemaVersion,
                command = WireValues.HeadRecenter,
                session_id = SessionId,
                sequence = sequence.Next(),
                timestamp_ms = NextTimestamp(),
                payload = new HeadRecenterPayloadDto { frame = "quest_local", orientation = orientation },
            });
        }

        public string BuildPose(Quaternion unityOrientation, long nowMs)
        {
            if (!CanSendPose) return null;
            QuaternionDto orientation = ToDto(QuestLocalPoseConverter.Convert(unityOrientation));
            return Encode(new HeadPoseCommandDto
            {
                schema_version = WireValues.SchemaVersion,
                command = WireValues.HeadPose,
                session_id = SessionId,
                sequence = sequence.Next(),
                timestamp_ms = NextTimestamp(),
                payload = new HeadPosePayloadDto { frame = "quest_local", orientation = orientation, position = null },
            });
        }

        public bool TryConsumePoseSlot(long nowMs)
        {
            if (!CanSendPose) return false;
            if (nowMs < nextPoseDeadlineMs) return false;
            nextPoseDeadlineMs = nowMs + PoseIntervalMilliseconds;
            return true;
        }

        // session.stop is deliberately best effort; transport cleanup is owned by the behaviour.
        public string BuildBestEffortStop()
        {
            if (!sessionConfirmed || string.IsNullOrEmpty(SessionId)) return null;
            return Encode(new SessionStopCommandDto
            {
                schema_version = WireValues.SchemaVersion,
                command = WireValues.SessionStop,
                session_id = SessionId,
                sequence = sequence.Next(),
                timestamp_ms = NextTimestamp(),
                payload = new EmptyPayloadDto(),
            });
        }

        public bool HandleEvent(string eventJson)
        {
            try
            {
                object decoded = WireCodec.DecodeEvent(eventJson);
                if (decoded is GatewayStateEventDto stateEvent)
                {
                    if (stateEvent.correlation.IsAvailable && stateEvent.correlation.SessionId != SessionId) return false;
                    switch (stateEvent.state)
                    {
                        case "AWAITING_RECENTER":
                            State = QuestHeadClientState.AwaitingRecenter;
                            sessionConfirmed = true;
                            return true;
                        case "HEAD_ACTIVE":
                            State = QuestHeadClientState.HeadActive;
                            sessionConfirmed = true;
                            nextPoseDeadlineMs = monotonicMilliseconds();
                            return true;
                        case "SAFE_STOPPED":
                        case "ESTOP_LATCHED":
                            State = QuestHeadClientState.SafeStopped;
                            return true;
                        case "IDLE":
                            State = QuestHeadClientState.Disconnected;
                            sessionConfirmed = false;
                            return true;
                    }
                }
                else if (decoded is CommandRejectedEventDto)
                {
                    State = QuestHeadClientState.SafeStopped;
                    LastError = "command.rejected";
                    return true;
                }
                return decoded is NeckTargetEventDto || decoded is SafetyStopEventDto;
            }
            catch (Exception exception)
            {
                State = QuestHeadClientState.SafeStopped;
                LastError = exception.Message;
                return false;
            }
        }

        public void Close()
        {
            State = QuestHeadClientState.Disconnected;
            sessionConfirmed = false;
        }

        private long NextTimestamp()
        {
            long now = monotonicMilliseconds();
            if (now <= lastTimestampMs) now = lastTimestampMs + 1;
            lastTimestampMs = now;
            return now;
        }

        private static long StopwatchMilliseconds()
        {
            return (long)(Stopwatch.GetTimestamp() * 1000.0 / Stopwatch.Frequency);
        }

        private static QuaternionDto ToDto(Quaternion orientation)
        {
            return new QuaternionDto { x = orientation.x, y = orientation.y, z = orientation.z, w = orientation.w };
        }

        private static string Encode(object command)
        {
            return WireCodec.EncodeCommand(command);
        }
    }
}
