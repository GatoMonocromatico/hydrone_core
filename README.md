# hydrone_core

Workspace ROS2 Humble do projeto Hydrone.

- `bridge`: sobe `mavros` para múltiplos veículos e traduz entre um
  protocolo ROS2 de alto nível e o MAVLink (via MAVROS).
- `bridge_msgs`: mensagens customizadas desse protocolo.

## Requisitos

- ROS2 Humble
- [mavros](https://github.com/mavlink/mavros) para ROS2 Humble
- colcon (`sudo apt install python3-colcon-common-extensions`)
- Um SITL (ArduPilot SITL) acessível via UDP
- `psutil` (`pip install psutil`), usado por `validate_hybrid_bridge.py`

## Estrutura

```
hydrone_core-main/
├── docs/
│   └── protocolo_hibrido_topicos_mensagens.md
└── src/
    ├── bridge/
    │   ├── config/
    │   │   └── missao_exemplo.yaml
    │   ├── launch/
    │   │   ├── iniciar_multiplos_uavs.launch.py
    │   │   ├── iniciar_ponte_hibrida.launch.py
    │   │   └── iniciar_missao_completa.launch.py
    │   └── scripts/
    │       ├── hybrid_bridge_node.py
    │       ├── validate_hybrid_bridge.py
    │       └── mission_planner_node.py
    └── bridge_msgs/
        └── msg/
            ├── WaypointCommand.msg
            └── MissionState.msg
```

## Build

```bash
colcon build --symlink-install
source install/setup.bash
```

## Uso

Subir `mavros` para os UAVs 1 e 2 (sem ponte):

```bash
ros2 launch bridge iniciar_multiplos_uavs.launch.py
```

### Ponte (ROS2 ↔ MAVLink via MAVROS)

O planejador publica intenções ("vá para este waypoint") em ROS2 puro.

A ponte traduz isso para o MAVROS/piloto automático e traz o estado de volta como tópico ROS2. Spec completa em
[`docs/protocolo_hibrido_topicos_mensagens.md`](docs/protocolo_hibrido_topicos_mensagens.md).

| Tópico | Sentido | Mensagem |
|---|---|---|
| `/hydrone/waypoint_cmd` | Planejador → Ponte → MAVROS → Pixhawk | `bridge_msgs/WaypointCommand` |
| `/hydrone/mission_state` | Pixhawk → MAVROS → Ponte → Planejador | `bridge_msgs/MissionState` |

Subir mavros + ponte para o par drone + barco, contra SITL local:

```bash
ros2 launch bridge iniciar_ponte_hibrida.launch.py \
    drone_fcu_url:=udp://:14550@ \
    boat_fcu_url:=udp://:14560@
```

Cada instância da ponte só reage a comandos cujo `vehicle_id` seja o dela
(`hydrone_drone` ou `hydrone_boat`).

### Planejador de missão

`mission_planner_node.py` lê uma lista ordenada de waypoints por veículo
de um YAML (formato em
[`config/missao_exemplo.yaml`](src/bridge/config/missao_exemplo.yaml)) e
avança automaticamente usando `last_cmd_id` (confirmação, com retentativa)
e `waypoint_reached` (chegada), respeitando `hold_time_s`.

```bash
ros2 launch bridge iniciar_missao_completa.launch.py \
    drone_fcu_url:=udp://:14550@ \
    boat_fcu_url:=udp://:14560@ \
    mission_file:=/caminho/para/sua_missao.yaml
```

> TODO: Validar com o MAVROS e SITL no ROS2 Humble. Verificar o funcionamento correto da máquna de estados.

### Validação ponta a ponta e medição de latência

```bash
ros2 run bridge validate_hybrid_bridge.py --ros-args \
    -p vehicle_id:=hydrone_drone \
    -p latitude:=-22.90 -p longitude:=-43.20 -p altitude:=30.0 \
    -p trials:=20
```

Imprime média, desvio padrão, percentis (p50/p95/p99) e pico da latência,
uso de CPU/RAM local (se `psutil` estiver instalado), e grava tudo em CSV
(`hybrid_bridge_latency.csv` por padrão, `-p output_csv:=...`). Metodologia
de medição detalhada em
[`docs/protocolo_hibrido_topicos_mensagens.md`](docs/protocolo_hibrido_topicos_mensagens.md).

| Parâmetro | Default | Descrição |
|---|---|---|
| `monitor_resources` | `true` | Amostra CPU/RAM locais durante o teste |
| `stress_mode` | `false` | Dispara o próximo comando sem esperar `interval_s` |

> TODO: Depois de rodar os útlimos testes no primeiro 'TODO', obtenha e altera os números de latência.