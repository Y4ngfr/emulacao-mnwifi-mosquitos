import socket
import struct
import collections
import wave

LISTEN_IP = "0.0.0.0"
LISTEN_PORT = 9001

CLOCK_RATE = 8000
CANAIS = 1
LARGURA = 2

ARQUIVO_SAIDA = "reconstruido.wav"
TIMEOUT_FIM = 1.0  # segundos sem pacote = fim do stream

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((LISTEN_IP, LISTEN_PORT))
sock.settimeout(TIMEOUT_FIM)

buffer = {}  # seq -> payload
recebidos = 0

print(f"Receptor RTP em {LISTEN_IP}:{LISTEN_PORT}...")

try:
    while True:
        try:
            data, _ = sock.recvfrom(2048)
            if len(data) < 12:
                continue

            seq, ts, ssrc = struct.unpack("!HII", data[2:12])
            payload = data[12:]

            if seq not in buffer:
                buffer[seq] = payload
                recebidos += 1

        except socket.timeout:
            # Nenhum pacote por TIMEOUT_FIM segundos → fim do stream
            if recebidos == 0:
                print("Nenhum pacote recebido. Aguardando...")
                continue
            print(f"\nTimeout. {recebidos} pacotes recebidos. Salvando...")
            break

except KeyboardInterrupt:
    print(f"\nInterrompido. {recebidos} pacotes recebidos. Salvando...")

# Reconstrói o WAV em ordem de sequence number
with wave.open(ARQUIVO_SAIDA, "wb") as wav:
    wav.setnchannels(CANAIS)
    wav.setsampwidth(LARGURA)
    wav.setframerate(CLOCK_RATE)

    for seq in sorted(buffer.keys()):
        wav.writeframes(buffer[seq])

print(f"Arquivo salvo: {ARQUIVO_SAIDA} ({len(buffer)} pacotes, "
      f"{sum(len(p) for p in buffer.values())} bytes de áudio)")