import paho.mqtt.client as mqtt

BROKERIP = "172.17.0.2"
TOPICO = "teste"

# Callback quando uma mensagem chega
def on_message(client, userdata, msg):
    contador = userdata
    print(f"{msg.topic}: {msg.payload.decode()}")
    contador += 1
    if contador == 10:
        print("10 mensagens recebidas")

if __name__ == "__main__":
    assinante_mqtt = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="assinante")
    contador = 0
    assinante_mqtt.on_message = on_message
    assinante_mqtt.user_data_set(contador)

    assinante_mqtt.connect(BROKERIP, 1883)
    assinante_mqtt.subscribe(TOPICO)

    print("Aguardando mensagens")
    assinante_mqtt.loop_forever()