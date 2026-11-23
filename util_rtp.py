import struct
import time

RTP_EXT_PROFILE = 0x4D51


def build_rtp_header(seq, timestamp, ssrc, payload_type, marker=0,
                     send_mono_ns=None, classe_verdadeira=0):
    if send_mono_ns is None:
        send_mono_ns = time.monotonic_ns()

    byte0 = 0x90
    byte1 = (marker << 7) | payload_type
    cabecalho = struct.pack("!BBHII", byte0, byte1,
                            seq & 0xFFFF, timestamp & 0xFFFFFFFF, ssrc)
    extensao = struct.pack(
        "!HHQI",
        RTP_EXT_PROFILE,
        3,
        send_mono_ns & 0xFFFFFFFFFFFFFFFF,
        classe_verdadeira & 0xFFFFFFFF,
    )
    return cabecalho + extensao


def iterar_pacotes_rtp(adpcm_bytes, taxa_amostragem, ssrc, payload_type,
                       amostras_por_bloco=160, classe_verdadeira=0):
    """
    Gerador: produz (pacote_rtp, duracao_s) um por vez.
    Quem consome decide quando enviar.
    """
    bytes_dados_por_bloco = amostras_por_bloco // 2
    tamanho_bloco = 4 + bytes_dados_por_bloco
    duracao_bloco_s = amostras_por_bloco / taxa_amostragem

    total_blocos = (len(adpcm_bytes) + tamanho_bloco - 1) // tamanho_bloco
    seq = 0
    timestamp = 0
    idx = 0
    i = 0

    while i < len(adpcm_bytes):
        bloco = adpcm_bytes[i:i + tamanho_bloco]
        if len(bloco) < 4:
            break

        eh_ultimo = (idx == total_blocos - 1)
        header = build_rtp_header(
            seq,
            timestamp,
            ssrc,
            payload_type,
            marker=1 if eh_ultimo else 0,
            classe_verdadeira=classe_verdadeira,
        )
        yield header + bloco, duracao_bloco_s

        i += tamanho_bloco
        seq = (seq + 1) & 0xFFFF
        timestamp = (timestamp + amostras_por_bloco) & 0xFFFFFFFF
        idx += 1