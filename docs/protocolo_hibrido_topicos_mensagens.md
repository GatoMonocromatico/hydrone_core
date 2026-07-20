# Protocolo híbrido ROS2 ↔ MAVLink com spec de tópicos e mensagens

Interface entre o **planejador de missão** (ROS2) e o **piloto automático**
(Pixhawk/SITL), mediada pelo **MAVROS**.

## Fluxo

```
Planejador        Ponte (bridge)                MAVROS              Pixhawk (SITL)
    |  /hydrone/waypoint_cmd    |                    |                    |
    |-------------------------->| mavros/setpoint_position/global         |
    |                           |------------------->|------------------->|
    |                           | mavros/state, mavros/global_position/global
    |  /hydrone/mission_state   |<-------------------|<--------------------|
    |<--------------------------|                    |                    |
```

## Tópicos do protocolo (global)

O campo `vehicle_id` identifica o destinatário (comando) ou a origem
(estado), permitindo ao planejador falar com qualquer veículo sem
conhecer a topologia interna do MAVROS.

| Tópico | Direção | Mensagem |
|---|---|---|
| `/hydrone/waypoint_cmd` | Planejador → Ponte → MAVROS → Pixhawk | `bridge_msgs/WaypointCommand` |
| `/hydrone/mission_state` | Pixhawk → MAVROS → Ponte → Planejador | `bridge_msgs/MissionState` |

- `/hydrone/waypoint_cmd`: publicado pelo planejador; assinado por cada
  instância da ponte (descarta comandos com `vehicle_id` diferente do seu).
- `/hydrone/mission_state`: publicado por cada instância da ponte;
  assinado pelo planejador e por ferramentas de validação.

## No MAVROS (dentro do namespace do veículo)

| Tópico/serviço | Direção | Mensagem |
|---|---|---|
| `mavros/setpoint_position/global` | Ponte → MAVROS | `geographic_msgs/GeoPoseStamped` |
| `mavros/state` | MAVROS → Ponte | `mavros_msgs/State` |
| `mavros/global_position/global` | MAVROS → Ponte | `sensor_msgs/NavSatFix` |
| `mavros/set_mode` (serviço) | Ponte → MAVROS | `mavros_msgs/srv/SetMode` |
| `mavros/cmd/arming` (serviço) | Ponte → MAVROS | `mavros_msgs/srv/CommandBool` |

## Mensagens customizadas

### `bridge_msgs/WaypointCommand`

| Campo | Tipo | Descrição |
|---|---|---|
| `header` | `std_msgs/Header` | Carimbo de tempo |
| `cmd_id` | `uint32` | Id de correlação, definido pelo planejador |
| `vehicle_id` | `string` | Veículo de destino |
| `latitude`/`longitude` | `float64` | Alvo (WGS84) |
| `altitude` | `float32` | Alvo, em metros |
| `hold_time_s` | `float32` | Tempo de permanência sobre o waypoint |

### `bridge_msgs/MissionState`

| Campo | Tipo | Descrição |
|---|---|---|
| `header` | `std_msgs/Header` | Carimbo de tempo |
| `vehicle_id` | `string` | Veículo de origem |
| `connected`/`armed`/`mode` | — | Espelham `mavros_msgs/State` |
| `latitude`/`longitude`/`altitude` | — | Posição atual |
| `last_cmd_id` | `uint32` | Último `cmd_id` aceito (0 = nenhum) |
| `target_latitude`/`target_longitude`/`target_altitude` | — | Alvo do último comando |
| `waypoint_reached` | `bool` | Dentro do raio de aceitação do alvo |

## QoS (ROS2/DDS)

| Tópico | Reliability | History | Durability | Por quê |
|---|---|---|---|---|
| `/hydrone/waypoint_cmd` | `RELIABLE` | `KEEP_LAST(10)` | `VOLATILE` | Perder um é pior que a latência extra |
| `/hydrone/mission_state` | `BEST_EFFORT` | `KEEP_LAST(1)` | `TRANSIENT_LOCAL` | A última amostra sempre substitui, sem fila acumulada |

Estrutura baseada em Silva Cotta et al. (*Sensors* 2023, 23, 9269) para QoS de
telemetria em DDS. O lado que fala com o MAVROS mantém QoS padrão.

## Confirmação de comando e latência

Dois sinais distintos em `MissionState`:

- **Comando confirmado**: `last_cmd_id` já reflete o `cmd_id` enviado. Ou seja, a
  ponte recebeu e repassou ao piloto automático.
- **Waypoint alcançado**: `waypoint_reached == true`, o veículo chegou
  fisicamente perto o suficiente do alvo.

A ponte publica a confirmação imediatamente ao aceitar o comando, fora do
ciclo periódico de telemetria e evita que a latência medida inclua o
período de publicação (`1 / state_publish_rate_hz`).

A latência de ida-e-volta é medida entre a publicação do comando e a
chegada da `MissionState` com o `last_cmd_id` correspondente.
`validate_hybrid_bridge.py` automatiza essa medição contra o SITL, usando
`time.monotonic()` (ponte e validador rodam no mesmo host, então um único
relógio.

## Referências

- Silva Cotta, J.L. et al. *Latency Reduction and Packet Synchronization
  in Low-Resource Devices Connected by DDS Networks in Autonomous UAVs*.
  Sensors 2023, 23, 9269. https://doi.org/10.3390/s23229269 — QoS de
  telemetria e metodologia de percentis/pico.
