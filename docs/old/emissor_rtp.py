import wave
import struct
import socket
import time

DURACAO_FRAME_MS =  20 # duração em ms de cada frame rtp (ou seja, cada frame lançado na rede, terá duração de 20ms de áudio)
SSRC = 0    # id do emissor (é possível múltiplos emissores), pode ser qualquer valor em uma faixa de 32 bits
PAYLOAD_TYPE = 96 # campo de 7 bits no cabeçalho RTP que diz ao receptor qual codec/format está dentro do payload daquele pacote
"""
0 = PCMU (G.711 µ-law, 8 kHz)
8 = PCMA (G.711 A-law, 8 kHz)
9 = G.722
10 = L16 (PCM 16 bits, estéreo)
11 = L16 (PCM 16 bits, mono)
14 = MPA (MPEG Audio)
26 = JPEG (vídeo)
96–127: dinâmicos
"""


def build_rtp_header(seq, ts, ssrc, pt, marker=0):
    byte0 = 0x80
    byte1 = (marker << 7) | pt
    return struct.pack("!BBHII", byte0, byte1,
                       seq & 0xFFFF, ts & 0xFFFFFFFF, ssrc)

def main():
    with wave.open("sample_pcm.wav", "rb") as wav:
        CLOCK_RATE = wav.getframerate()
        CANAIS = wav.getnchannels()
        LARGURA = wav.getsampwidth()
        total_frames = wav.getnframes()

        pcm_bytes = wav.readframes(total_frames)


    print(f"WAV: {CLOCK_RATE} Hz, {CANAIS} canal(is), "
        f"{LARGURA*8} bits, {total_frames} amostras, "
        f"{len(pcm_bytes)} bytes")

    amostras_por_frame = CLOCK_RATE * DURACAO_FRAME_MS // 1000
    bytes_por_frame = amostras_por_frame * CANAIS * LARGURA

    # Socket UDP
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # Construção manual do cabeçalho
    n_seq = 0     # número de sequencia do quadro para reconstrução no receptor
    timestamp = 0
    # intervalo = DURACAO_FRAME_MS / 1000.0

    i = 0
    while i < len(pcm_bytes):
        # Fatia um frame
        frame = pcm_bytes[i:(i + bytes_por_frame)]
        if len(frame) == 0:
            break

        header = build_rtp_header(n_seq, timestamp, SSRC, PAYLOAD_TYPE)
        sock.sendto(header + frame, ("127.0.0.1", 9001))

        i += bytes_por_frame
        n_seq = (n_seq + 1) & 0xFFFF
        timestamp = (timestamp + amostras_por_frame) & 0xFFFFFFFF

        # 20 ms por pacote
        time.sleep(0.02)
        

if __name__ == "__main__":
    main()
