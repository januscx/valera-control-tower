using System;
using System.Threading;
using System.Threading.Tasks;
using Valera.QuestHeadClient.Transport;

namespace Valera.QuestHeadClient.Transport
{
    public sealed class VrGatewayWebSocket : IDisposable
    {
        private IQuestTransport transport;
        private CancellationTokenSource receiveCancellation;
        private Task receiveTask;
        private bool disposed;

        public bool IsConnected => transport != null && transport.IsOpen;

        public event Action<string> OnEventReceived;
        public event Action OnDisconnected;

        private const string CommandTopic = "/valera/vr_gateway/command";
        private const string EventTopic = "/valera/vr_gateway/event";
        private const string CommandType = "std_msgs/msg/String";

        public async Task Connect(string url)
        {
            ThrowIfDisposed();
            await DisconnectInternalAsync();

            transport = new ClientWebSocketQuestTransport();
            receiveCancellation = new CancellationTokenSource();
            await transport.ConnectAsync(new Uri(url), receiveCancellation.Token);
            await transport.SendAsync(
                RosbridgeEnvelopeCodec.EncodeAdvertise(CommandTopic, CommandType),
                receiveCancellation.Token);
            await transport.SendAsync(
                RosbridgeEnvelopeCodec.EncodeSubscribe(EventTopic),
                receiveCancellation.Token);
            receiveTask = ReceiveLoop(receiveCancellation.Token);
        }

        public async Task SendCommand(string innerJson)
        {
            if (disposed || transport == null || !transport.IsOpen) return;
            try
            {
                string envelope = RosbridgeEnvelopeCodec.EncodePublish(CommandTopic, innerJson);
                await transport.SendAsync(envelope, CancellationToken.None);
            }
            catch
            {
                OnDisconnected?.Invoke();
            }
        }

        public async Task Disconnect()
        {
            await DisconnectInternalAsync();
        }

        private async Task DisconnectInternalAsync()
        {
            receiveCancellation?.Cancel();
            try
            {
                if (receiveTask != null) await receiveTask;
            }
            catch { }
            if (transport != null)
            {
                try { await transport.CloseAsync(CancellationToken.None); } catch { }
                transport.Dispose();
                transport = null;
            }
            receiveCancellation?.Dispose();
            receiveCancellation = null;
            receiveTask = null;
        }

        private async Task ReceiveLoop(CancellationToken cancellationToken)
        {
            try
            {
                while (!cancellationToken.IsCancellationRequested)
                {
                    string envelope = await transport.ReceiveAsync(cancellationToken);
                    if (envelope == null)
                    {
                        OnDisconnected?.Invoke();
                        return;
                    }
                    OnEventReceived?.Invoke(
                        RosbridgeEnvelopeCodec.DecodeMessageData(envelope));
                }
            }
            catch (OperationCanceledException) { }
            catch
            {
                OnDisconnected?.Invoke();
            }
        }

        private void ThrowIfDisposed()
        {
            if (disposed) throw new ObjectDisposedException(nameof(VrGatewayWebSocket));
        }

        public void Dispose()
        {
            if (disposed) return;
            disposed = true;
            receiveCancellation?.Cancel();
            receiveCancellation?.Dispose();
            transport?.Dispose();
        }
    }
}
