Nesse tutoria descrevo a melhor forma de instalar e rodar o mininet wifi em container docker.

1. Baixar o repositório oficial

git clone https://github.com/intrig-unicamp/mininet-wifi.git

O repositório tem o dockerfile para a instalação.

2. Modificar o Dockerfile. Adicionar a seguinte linha:

RUN apt-get clean && rm -rf /var/lib/apt/lists/* && apt-get update

Logo antes da linha de instalação do Dockerfile: RUN util/install.sh -Wlnfv6

3. Inicializar os módulos de kernel necessários no sistema. Esse passo é obrigatório, pois carrega os módulos de kernel que o container precisa para utilizar as implementações de dispositivos emuladas do mininet wifi. Para isso basta rodar os comandos no host:

sudo modprobe openvswitch
sudo modprobe mac80211_hwsim

E para verificar se o módulo foi carregado (basta que haja saída):

lsmod | grep openvswitch
lsmod | grep mac80211_hwsim

4. Criar a imagem:

docker build -t mn-wifi:v1 .

5. Criar o container. Para isso vamos utilizar o comando recomendado pelo próprio repositório:

docker run -it --rm --privileged --env="DISPLAY" --env="QT_X11_NO_MITSHM=1" -v /tmp/.X11-unix:/tmp/.X11-unix:rw --net host -v /sys/:/sys -v /lib/modules:/lib/modules -v /sys/kernel/debug:/sys/kernel/debug -v /var/run/netns:/var/run/netns -v /var/run/docker.sock:/var/run/docker.sock -v ".:/app/workspace"  mn-wifi:v1

Este comando inicia um container efemero do mininet wifi, em modo privilegiado, que é obrigatório para o Mininet Wifi utilizar módulos do kernel do host.

Os argumentos -v são mapeamentos de diretórios do host para diretórios dentro do container. Atenção especial para -v ".:/app/workspace" que mapeia o diretório atual para o diretório /app/workspace no container

6. Dentro do container é necessário rodar o comando:

service openvswitch-switch start

7. Para inicializar o Mininet-Wifi e verificar se tudo funcionou basta rodar:

mn --wifi

8. Dentro do container para iniciar o frontend:

cd /app/workspace/frontend && npm install && npm run dev
Em outro terminal do container:
cd /app/workspace
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000